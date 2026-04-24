# Agent CLI Mode for dictpro

**Status**: Approved design, ready for implementation plan
**Date**: 2026-04-22

## Goal

让 `dictpro` 原本只能人机交互的命令行工具同时能被 AI agent 当作结构化数据源和批量写入工具调用，覆盖两种场景：

- **A. 单次查询**：agent 给一个词，拿回结构化 JSON，可以选择同时写入 `.md` 生词本
- **B. 批量查询**：agent 给一串词（文件或 stdin），拿回流式 NDJSON，可以选择按策略批量写入 `.md`

交互模式（无 `-q` / `-b`）完全保留，不破坏现有人类用户。

## 设计原则

遵循 "smart model dump tools"：

1. **Flag 含义自解释**，agent 不用记反向/复合逻辑
2. **行为由 flag 存在性决定**，而非由值翻转（e.g. 没给 `--pick` 就是不写，不需要 `--no-write`）
3. **Agent 模式下 stdout 永远是机器可读**（JSON / NDJSON），**stderr 永远是人类可读**诊断；交互模式保持混合输出（原行为）
4. **Exit code 有语义**，agent 能据此分支
5. **能不让 agent 选就不让选**——工具替 agent 做好合理默认

## 参数设计

### 新增参数（3 个）

| Flag | 含义 | 备注 |
|---|---|---|
| `-q, --query WORD` | 单次查询，进入 agent 模式 | 与 `--batch` 互斥（argparse mutually exclusive group） |
| `-b, --batch FILE` | 批量查询，`FILE` 是文件路径或 `-` 表示 stdin | 每行一个词，空行和前后空白跳过 |
| `--pick SPEC` | 选哪些义项写入 md。**缺省 = 不写**（即便 `-o` 存在） | `SPEC` 取值见下 |

`--pick SPEC` 合法值：

- `0` 或 `0,2,5` — 显式义项编号，**仅 `-q` 可用**（批量时每词编号不同，无意义）
- `first` — 每个词的 sense 0
- `first-per-pos` — 每个词、每个词性的第一条 sense
- `all` — 该词全部 sense

批量模式下传 `0,2,5` → argparse 之后立刻校验，exit 1 + stderr 提示，不发起任何网络请求。

### 优化既有参数

| 动作 | 原 flag | 新 flag | 说明 |
|---|---|---|---|
| 合并 | `--name NAME` + `--path PATH` | `-o, --output PATH` | 如果 `PATH` 没有 `.md` 后缀则自动补 `.md`；父目录必须存在否则 exit 1。相对/绝对路径都支持 |
| 重命名 | `--head` | `--rewrite-header` | 自解释 |
| 保持 | `--audio / --no-audio` | — | 不变 |
| 保持 | `--synonym / --no-synonym` | — | 不变 |

**删除**（不保留 deprecated 别名）：`--name`、`--path`、`--head`

### 模式判定

- 给了 `-q` 或 `-b` → **agent 模式**（非交互，stdout 输出 JSON/NDJSON）
- 两个都没给 → **交互模式**（原行为不变）
- 给了 `-q` + `-b` → argparse 在 parse 阶段拒绝

### 行为矩阵

| 调用 | 写 md？ | stdout |
|---|---|---|
| `dictpro -q serendipity` | 否 | 完整 JSON |
| `dictpro -q serendipity --pick 0,2 -o vocab` | 是 | 完整 JSON（含 `written` 字段） |
| `dictpro -q serendipity -o vocab`（无 `--pick`） | ❌ exit 1 | — |
| `dictpro -b words.txt` | 否 | NDJSON |
| `dictpro -b words.txt --pick first -o vocab` | 是 | NDJSON（每行含 `written`） |
| `dictpro -b - --pick first -o vocab`（stdin） | 是 | NDJSON |
| `dictpro -o vocab`（无 `-q`/`-b`） | — | 交互模式，原行为 |

## JSON Schema

单次查询 (`-q`) 直出一个 JSON 对象；批量 (`-b`) 输出 NDJSON，每行一个以下对象：

```json
{
  "word": "serendipity",
  "ok": true,
  "senses": [
    {"i": 0, "pos": "noun", "text": "the fact of finding interesting or valuable things by chance"}
  ],
  "inflections": {"noun": ["serendipities"]},
  "synonyms":    {"noun": ["chance", "fortune"]},
  "pronunciations": {
    "noun": [[
      {"region": "US", "ipa": "/ˌser.ənˈdɪp.ə.t̬i/", "audio": "https://..."},
      {"region": "UK", "ipa": "/ˌser.ənˈdɪp.ɪ.ti/", "audio": "https://..."}
    ]]
  },
  "errors":  {"wiktionary": "404"},
  "written": [0]
}
```

字段约定：

- `word` — 永远存在，回显输入
- `ok` — Cambridge 拿到至少一条 sense 为 `true`，否则 `false`
- `senses[].i` — 全局连续编号，**与 `--pick 0,2` 中数字一一对应**
- `inflections` / `synonyms` / `pronunciations` — 对应源失败时该键整体省略
- `errors` — 仅列失败的源；全部成功则该键省略
- `written` — 本次写入 md 的 sense 索引数组；**没写 md 时该键省略**

pronunciations 的嵌套结构 `pos → groups → prons` 1:1 对应现有数据模型 `WordEntry.pronunciations`，不做扁平化。

## 批量错误处理

**核心判断**：区分"数据层失败"和"工具层失败"。

| 类型 | 例子 | 处理 | stdout | exit |
|---|---|---|---|---|
| 单词查不到 | Cambridge 404 | 算数据 | `{"ok": false, "errors": {...}}` | 正常 |
| 单源瞬时失败 | Wiktionary 超时 3 次 | 算数据 | `ok` 可能仍 true，`errors` 有记 | 正常 |
| 输入行非法 | 空行、含控制字符 | 跳过 + stderr 一行 warning | 不产出该行 | 正常 |
| 输出 IO 失败 | 磁盘满、无权限 | 工具层，立即 abort | 刷完已有缓冲 | `1` |
| 整批全挂 | 所有词 `ok: false` | 跑完后统一判定 | 照常每行 NDJSON | `2` |

**Exit code**：
- `0` — 至少一个词成功
- `1` — 用法错误 / IO 错误
- `2` — 所有词都失败（帮 agent 区分"网络断了 vs 词不存在"）

**NDJSON 流式 flush**：每查完一个词 `print(json); flush()`。agent 可边读边处理，大批量不爆内存。

**不引入 `--on-error` flag**——"数据失败继续、工具失败 abort"是唯一合理解，不让 agent 选。

## 架构影响

当前 `dictpro/cli.py` 强交互，逻辑如下：
- `_resolve_path` 在缺参数时提示用户（agent 模式会死锁 → 需绕过）
- `_lookup_and_write` 打印义项 + 等 `pick>` 输入 + 写文件（agent 需要重新组合：查询、序列化、可选写入）

重构方向：

1. 把 `_lookup_and_write` 里的三件事拆开：
   - `lookup(word) -> LookupResult`（已有 `concurrent.fetch_all`，直接复用）
   - `result_to_json(result) -> dict`（**新增**）
   - `write_senses(result, indices, out_file, opts)`（从 `_lookup_and_write` 抽出）
2. `cli.main` 按模式分派：
   - agent 单查分支：`lookup` → `result_to_json`（填 `written` 如果写了） → `print(json.dumps(...))`
   - agent 批量分支：迭代输入 → 对每行调 agent 单查分支 → flush
   - 交互模式：保留现有 `_lookup_and_write` 流程
3. `renderer.py` 不需要大改，只是被新的 `write_senses` helper 调用
4. `--pick SPEC` 解析抽一个函数 `parse_pick_spec(s, mode) -> PickStrategy`，单查/批量共用

## 测试策略

- 单元测试：
  - `parse_pick_spec` 的合法/非法输入
  - `result_to_json` 对 fixture `LookupResult` 的序列化
  - 部分源失败时 `errors` 字段正确出现/省略
- 集成测试（mock `http_get`）：
  - `dictpro -q WORD` → stdout 符合 schema，exit 0
  - `dictpro -q WORD --pick 0 -o tmp.md` → md 有内容 + stdout JSON 有 `written: [0]`
  - `dictpro -b -` 从 stdin 读 3 个词（1 成功 + 1 not found + 1 空行）→ 2 行 NDJSON + 1 行 stderr warning，exit 0
  - 所有词都 not found → exit 2
  - `-o` 指向不存在目录 → exit 1，stderr 清楚
- 既有测试不应破坏（交互模式代码路径未动）

## 不在本次 scope

- MCP server 封装（方案 3，未来）
- 文本 extract（方案 3，未来）
- `--pick context:"..."`（让 LLM 挑义项，未来）
- `--columns` DSL（等有第 3 个可选列再说）
