# Dictionary Pro

[English](README.md) | **简体中文**

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Version](https://img.shields.io/badge/version-0.2.0-green) ![Agent Ready](https://img.shields.io/badge/agent--ready-skill-purple)

命令行查词工具，自动把挑中的释义整理成 Markdown 生词本。

适合精读外刊、论文、原版书时边读边收词——查一次、挑想要的义项、结果直接追加到 `.md` 文件，用 Obsidian / Typora 打开就是一张整洁的生词表。

> 也自带 skill，可供 Claude Code 等 agent 调用，详见 [部署 Skill](#部署-skill)。

## 为什么用它

- **一次查三源**：Cambridge（释义 + 发音）、Wiktionary（动词变位 / 复数）、FreeThesaurus（同义词）并发请求，速度和单查一家差不多
- **只收你想要的**：义项按词性分组列出，手动挑选编号，不会把整页词典塞进笔记
- **输出即用**：Markdown 表格，含 IPA 音频超链接和 Cambridge 页面跳转

## 效果预览

终端交互：

```
word> serendipity
--------------------
serendipity
noun: 0 the fact of finding interesting or valuable things by chance
pick> 0
word> /q
```

生成的 `vocab.md`：

| Word | Pos | Def | Syn | Verbs | Pron | Web |
|---|---|---|---|---|---|---|
| serendipity | noun | the fact of finding interesting or valuable things by chance | chance; fortune | serendipities | US: [/ˌser.ənˈdɪp.ə.t̬i/](...) | [^_^](https://...) |

## 安装

需要 Python 3.10+。

```bash
git clone <repo-url>
cd dictionary_pro
pip install -e .
```

验证：

```bash
dictpro --help
# 或 python main.py --help
```

## 60 秒上手

```bash
dictpro -o vocab
```

然后：

1. 在 `word>` 提示符下输入要查的词，回车
2. 看到义项列表后，在 `pick>` 提示符下输入想保存的编号（如 `0`）
3. 回到 `word>` 继续输入下一个词，或 `/q` 退出
4. 打开 `./vocab.md` 查看结果

## 交互速查

两种提示符：

- `word> ` — 输入要查的词
- `pick> ` — 输入要保存的义项编号

| 提示符 | 输入 | 含义 |
|---|---|---|
| `word> ` | `word` | 查一个词 |
| `word> ` | `w1,w2,w3` | 一次查多个词（逗号分隔） |
| `word> ` | `/q` | 退出 |
| `pick> ` | `0` / `0,2,5` | 把第 N 个义项写入文件，可多选（逗号分隔） |
| `pick> ` | `/x` | 当前词一个都不要，跳过 |

## 命令行参数

| 参数 | 说明 |
|---|---|
| `-o, --output PATH` | 输出 md 路径。无 `.md` 后缀则自动补；父目录必须存在 |
| `--no-audio` | 不要发音列 |
| `--no-synonym` | 不要同义词列 |
| `--rewrite-header` | 强制重写表头（默认追加到已有文件时不重复写） |

不给 `-o` 时，启动后会交互式询问文件名。

想让 agent / 脚本调用，见下面 [部署 Skill](#部署-skill)。

## 输出说明

表头字段：

- **Word**：单词
- **Pos**：词性
- **Def**：选中的释义
- **Syn**：同词性同义词
- **Verbs**：屈折形式（过去式、复数等）
- **Pron**：US / UK 发音，IPA 文字本身是音频链接
- **Web**：跳转到 Cambridge 原页面

同一个文件可以多次运行 `dictpro` 追加内容，表头只会写一次。

## 常用场景

```bash
# 为一本书建生词表
dictpro -o gatsby

# 只要释义和同义词，不要发音列
dictpro -o quick --no-audio

# 继续往旧文件追加，但想重新写一次表头
dictpro -o gatsby --rewrite-header
```

## 部署 Skill

项目自带一个 skill，让 agent 知道如何调用 dictpro。

### Claude Code 
```bash
# 把 skill 链接到 Claude Code 的 skills 目录
ln -s "$(pwd)/skills/use-dictpro" ~/.claude/skills/use-dictpro
```

之后在 Claude Code 会话里，agent 就能自动发现并使用 `dictpro -q` / `-b`，无需手动告知用法。

### Skill 功能

两个 flag：

| Flag | 做什么 |
|---|---|
| `-q WORD` | 查一个词，JSON 打到 stdout |
| `-b FILE` | 批量查，`FILE` 是路径或 `-`（stdin），每行一词，流式 NDJSON 输出 |

典型调用：

```bash
# 查一个词
dictpro -q serendipity

# 批量查
dictpro -b words.txt

# stdin 批量
cat words.txt | dictpro -b -
```

stdout 拿到的 JSON（`-q serendipity` 为例）：

```json
{
  "word": "serendipity",
  "ok": true,
  "senses": [{"i": 0, "pos": "noun", "text": "the fact of finding ..."}],
  "inflections": {"noun": ["serendipities"]},
  "synonyms": {"noun": ["chance", "fortune"]},
  "pronunciations": {"noun": [[{"region": "US", "ipa": "/...", "audio": "..."}]]}
}
```

`errors` 字段只在某个数据源失败时出现；`inflections`、`synonyms`、`pronunciations` 为空时省略。

Exit code 三档：

- `0` — 至少一个词查成功
- `1` — IO 错
- `2` — 全部词都查不到（agent 能据此区分"词没有"和"网络挂了"）

批量走的是 NDJSON，**每查完一个词立刻 flush 一行**，可流式消费。stdout 永远是机器可读（JSON / NDJSON），人类可读的诊断都在 stderr。

## 常见问题

**提示 `Word not found`**
三个源都没查到。检查拼写，或该词本身是专有名词 / 网络新词。

**网络超时**
内置重试，偶发失败直接再输入一次即可。长期失败检查代理。

**义项太多怎么挑**
编号是全局连续的，跨词性也能选：比如想同时收 `noun: 0` 和 `verb: 3`，输入 `0,3`。

## 项目结构

```
dictpro/
  cli.py          # 交互入口 / 参数分发
  agent.py        # -q / -b 的 JSON 输出逻辑
  fetchers.py     # 带重试的 HTTP 层
  concurrent.py   # 三源并发调度
  parsers/        # cambridge / wiktionary / thesaurus 各自解析
  renderer.py     # Markdown 表格渲染
  models.py       # 数据结构
```

想加数据源：在 `parsers/` 新增一个解析器，在 `concurrent.py` 注册即可。
