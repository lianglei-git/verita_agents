# en-syntax-tagger

按 **Prompt 模板差异** 提供三个 API 版本。包版本（`config.json`）与 `api_version` 分离。

## 版本对照（解决什么问题）

| API | 别名 | Prompt 风格 | 解决的问题 |
|-----|------|-------------|------------|
| **v1** | `a` / `academic` | 详细学术版 | 用标准缩写(S/V/O…)与短语标记，输出主干、修饰、特殊结构、树形、成分表、可选语义角色 → **结构最完整，适合精读/教研** |
| **v2** | `b` / `teaching` | 对比学习版 | 主干一句话 + 片段对照表 + 结构树 + 难点说明 → **适合教学对照、降低阅读成本** |
| **v3** | `c` / `json` | JSON 数据版 | clauses / constituents（含 `start_index`/`end_index`）/ chunks / tokens / grammars → **适合程序消费、高亮对齐** |

三者均附带 **spaCy `spacy_tokens`**（pos/tag/dep）。

设计原则（见各版 `prompt.txt`）：

```
明确任务 + 指定格式 + 标注体系 + JSON 输出形状
```

## 调用

```python
from agent import run

run("The fox jumps.")                    # 默认 v1；native_lang=中文, learn_lang=英语
run("The fox jumps.", version="v2")
run("The fox jumps.", version="v3")
run("The fox jumps.", version="teaching")  # → v2
run(
    "The fox jumps.",
    version="v1",
    native_lang="中文",   # 讲解/翻译用语
    learn_lang="英语",    # 被分析句子语言
)
```

`options` / kwargs：

| 字段 | 默认 | 说明 |
|------|------|------|
| `native_lang` | `中文` | 学习者母语；翻译与说明性文字 |
| `learn_lang` | `英语` | 目标语；被分析句子语言 |

术语标记固定用英文符号（S/V/O、NP/VP…），说明文字跟 `native_lang`。
```bash
python agent.py --version v1 "Although she was tired, she kept working."
python agent.py --version v2 "..."
python agent.py --version v3 "..."
```

## 契约文件

| 版本 | Prompt | 输入 schema | 输出 schema |
|------|--------|-------------|-------------|
| v1 | [`versions/v1/prompt.txt`](versions/v1/prompt.txt) | `input.schema.json` | `output.schema.json` |
| v2 | [`versions/v2/prompt.txt`](versions/v2/prompt.txt) | 同上 | 同上 |
| v3 | [`versions/v3/prompt.txt`](versions/v3/prompt.txt) | 同上 | 同上 |

共享运行时：[`versions/common.py`](versions/common.py)（spaCy + LLM）。

## 目录

```
en-syntax-tagger/
  agent.py
  spacy_tokens.py
  versions/
    common.py
    registry.py
    v1/  # academic
    v2/  # teaching
    v3/  # json_data
```
