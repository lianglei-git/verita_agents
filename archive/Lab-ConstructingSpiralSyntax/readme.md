# EGP 实验工作流说明

本目录用于实验性构建一套面向 EGP 语法点的“螺旋学习路径”工作流。它不是正式版三阶段管线的替代物，而是一个更灵活、更适合快速试验 prompt、模型和排序策略的实验场。

核心目标是：

- 

- 在同分条目之间进一步细排，减少路径中的并列和不稳定顺序。
- 对最终路径做抽样质检，判断它是否符合“先简后复、模块递进、螺旋回环”的教学逻辑。
- 提供一个轻量可视化页面，方便人工浏览和复核。

## 功能介绍

### 1. `main.py`

主入口，负责 Step 1 排序。

- `plugin=score`
  - 逐条调用 LLM，为每个 EGP 条目生成 `score`。
  - 分数越小，表示越应该更早进入当前等级学习路径。
  - 输出到 `output/<LEVEL>/latest.json` 以及带时间戳的结果文件。

- `plugin=full-sort`
  - 一次性将全量 EGP 条目交给 LLM 做整体排序。
  - 若全量返回格式非法，会先尝试让 LLM 修复格式。
  - 若仍失败，则回退到逐条评分补齐缺失项。
  - 输出到 `output/<LEVEL>/full_sort_latest.json` 以及带时间戳的结果文件。
  - 若全量排序存在明显异常，还会额外写出 `失败.json` 方便排查。

### 2. `phase2_same_score_order.py`

Step 2，同分组细排。

- 输入通常来自 Step 1 的 `latest.json`。
- 将 `llm_score` 相同的条目分组。
- 可选：
  - 无 LLM：按 `egp_id` 尾号稳定排序。
  - 有 LLM：对同分组做组内螺旋学习排序。
- 输出到：
  - `output/<LEVEL>/phase2_same_score_latest.json`
  - `output/<LEVEL>/phase2_same_score_order_<timestamp>.json`

### 3. `phase3_path_check.py`

Step 3，学习路径抽样校验。

- 对 Step 1 或 Step 2 的学习路径抽样。
- 让 LLM 判断每段路径是否符合螺旋学习逻辑。
- 输出：
  - 置信度
  - 问题列表
  - 中文整体评价
  - Markdown 报告
- 默认优先读取：
  - `phase2_same_score_latest.json`
  - 若不存在，则回退到 `latest.json`
- 输出到：
  - `output/<LEVEL>/phase3_path_check_latest.md`
  - `output/<LEVEL>/phase3_path_check_<timestamp>.md`

### 4. `viewer.py`

本地 HTML 浏览器，用于查看各等级输出结果。

- 浏览 `output/` 下不同等级的 JSON 文件。
- 展示 metadata、排序结果、分数、理由等。
- 适合人工巡检和快速比较不同实验结果。

### 5. `config.py`

集中管理：

- LLM 配置
- 模型默认值
- prompt 模板
- 不同 CEFR 等级的评分策略文本
- 输出目录约定

## 工作流工作方式

这套实验工作流可以理解为一个 3 步闭环：

### 第一步：粗排序 / 主排序

由 `main.py` 完成。

- 输入：
  - 默认是 EGP CSV
  - 也支持读取已有 JSON 结果继续处理
- 输出：
  - 每个条目的 `llm_score`
  - 以及带 `metadata` 的完整结果文档

这一阶段的目标不是绝对正确，而是先得到一个“整体可用的初版路径”。

### 第二步：同分组细排

由 `phase2_same_score_order.py` 完成。

- 只处理 Step 1 中 `score` 相同的组。
- 目标是把“同分并列”打散成更稳定的组内顺序。
- 这样最终路径更平滑，也更方便后续人工审阅。

### 第三步：路径抽样质检

由 `phase3_path_check.py` 完成。

- 不直接重排路径，而是检查路径质量。
- 通过多次随机抽样，让 LLM 判断局部路径是否合理。
- 若置信度低，就说明：
  - prompt 可能不够清晰
  - 模块聚类不够稳定
  - 或某些语法块顺序明显违背教学逻辑

### 第四步：人工复核与可视化

由 `viewer.py` 和人工分析共同完成。

- 打开本地页面查看 JSON 结果。
- 结合 `phase3_path_check_latest.md` 中的问题说明，回头修改：
  - `config.py` 的 prompt
  - `main.py` 的输出策略
  - `phase2_same_score_order.py` 的组内排序策略

换句话说，这套工作流本质上是：

`生成初版路径 -> 细排 -> 质检 -> 人工修正 -> 再跑`

## 推荐使用方式

### 1. 先跑全量排序

```bash
python main.py --level B1 --plugin full-sort
```

### 2. 若需要进一步稳定同分组

```bash
python phase2_same_score_order.py --level B1 --llm
```

### 3. 做路径抽样校验

```bash
python phase3_path_check.py --level B1 --input output/B1/full_sort_latest.json
```

### 4. 打开可视化结果

```bash
python viewer.py
```

## 主要输出文件

以 `B1` 为例，常见文件如下：

- `output/B1/latest.json`
  - Step 1 逐条评分结果
- `output/B1/full_sort_latest.json`
  - Step 1 全量排序结果
- `output/B1/phase2_same_score_latest.json`
  - Step 2 同分组细排结果
- `output/B1/phase3_path_check_latest.md`
  - Step 3 抽样质检报告
- `output/B1/失败.json`
  - 全量排序异常时保留的失败样本

## 工作流修正文件命名规范

为了避免“人工修正文件”命名混乱，建议统一使用 **agent 命名**。

### Agent 角色命名

建议固定以下 agent 名称：

- `score-agent`
  - 负责 Step 1 打分/全量排序相关修正
- `tie-break-agent`
  - 负责 Step 2 同分组细排相关修正
- `path-check-agent`
  - 负责 Step 3 路径质检与报告修正
- `viewer-agent`
  - 负责可视化展示与人工复核支持相关修正

### 修正文件统一命名格式

建议统一格式：

```text
workflow_fix_<agent-name>_<level>_<yyyymmdd_hhmmss>.<ext>
```

例如：

- `workflow_fix_score-agent_B1_20260312_143000.md`
- `workflow_fix_tie-break-agent_B1_20260312_143500.json`
- `workflow_fix_path-check-agent_C2_20260312_150200.md`

### 命名含义

- `workflow_fix`
  - 表明这是对实验工作流的修正文件
- `<agent-name>`
  - 表明修正责任归属到哪个 agent
- `<level>`
  - 表明对应 CEFR 等级
- `<timestamp>`
  - 表明生成时间，避免覆盖
- `<ext>`
  - `md` 用于说明文档
  - `json` 用于结构化修正内容
  - `txt` 用于临时记录

## 推荐落地规则

如果你后续真的要持续保存“工作流修正说明”，建议：

- 说明类文件统一用：
  - `workflow_fix_<agent-name>_<level>_<timestamp>.md`
- 结构化修正结果统一用：
  - `workflow_fix_<agent-name>_<level>_<timestamp>.json`
- 不再使用过于模糊的命名，如：
  - `失败2.json`
  - `新版本.md`
  - `改好了.json`

这样后续无论是人工追踪，还是 agent 自动处理，都更容易知道：

- 这个文件修的是什么阶段
- 是谁负责修的
- 对应哪个等级
- 是什么时候生成的
