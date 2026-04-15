# Built-Knowledge-Graph — EGP 英语语法知识图谱

基于 EGP（English Grammar Profile）数据构建的英语语法知识图谱，覆盖 A1–C2 全级别共 1222 个语法点，支持结构化查询、学习路径生成与交互式探索。

---

## 项目定位

本项目的核心目标是构建一个**结构稳定、关系可解释、可供下游教学系统使用的英语语法知识底座**，而不是自动生成最优跨类别学习路径。

第一阶段解决的是「结构化知识底座」问题：

- 统一管理 A1–C2 全部语法点的层级结构
- 按 CEFR 等级、大类、子类进行浏览与检索
- 生成稳定可复现的分级学习顺序
- 为教学产品、可视化工具提供结构化数据

---

## 数据链路

```
Lab-ConstructingSpiralSyntax/output/<LEVEL>/phase1/full_sort_latest.json
        ↓  step0_build_sorted_array.py
output/A1_C2_sorted.json          ← 权威输入源（A1→C2 有序数组）
        ↓  step2_parse_egp.py
GrammarPointData 列表
        ↓  step3_build_graph.py
NetworkX 知识图谱 (G)
        ↓  step5 / step7
结构化输出文件 + 学习路径 JSON
```

`A1_C2_sorted.json` 是整个系统的单一权威数据源：每个等级内按 `llm_score` 升序排列，忠实保留 Lab 阶段产出的学习顺序。

---

## 构建流程

| 步骤 | 文件 | 说明 |
|------|------|------|
| Step 0 | `step0_build_sorted_array.py` | 合并各等级 `full_sort_latest.json` → `A1_C2_sorted.json` |
| Step 1 | `step1_ontology.py` | 定义本体：实体类型、关系类型、CEFR 等级 |
| Step 2 | `step2_parse_egp.py` | 从 `A1_C2_sorted.json` 解析为 `GrammarPointData` 列表 |
| Step 3 | `step3_build_graph.py` | 构建 NetworkX 有向图，推导 PREREQUISITE 关系 |
| Step 4 | `step4_query.py` | 查询示例：等级概览、语法点详情、前置依赖链 |
| Step 5 | `step5_export.py` | 导出 JSON / CSV / Neo4j Cypher |
| Step 6 | `step6_visualize.py` | 生成 PyVis 交互式 HTML 可视化 |
| Step 7 | `step7_learning_paths.py` | 生成多维度学习路径（按等级、主题、范围） |
| Step 8 | `step8_llm_annotate.py` | （可选）LLM 辅助标注跨类前置依赖候选 |
| Step 9 | `step9_merge_annotations.py` | 合并 LLM 标注结果，计算前置依赖闭包 |
| Step 10 | `step10_path_explorer.py` | 交互式 Web 探索器（Flask，端口 5002） |

---

## 快速开始

### 完整构建

```bash
# 标准构建（不含可选关键词关联）
python main.py

# 包含 RELATED_BY_KEYWORD 辅助关系（供可视化探索用）
python main.py --with-kw

# 跳过可视化（仅生成数据文件）
python main.py --no-viz
```

### 启动交互式探索器

```bash
python step10_path_explorer.py
# 访问 http://localhost:5002
```

---

## 图谱规模

| 维度 | 数量 |
|------|------|
| CEFR 等级 | 6（A1 / A2 / B1 / B2 / C1 / C2） |
| 语法大类（SuperCategory） | 19 |
| 语法子类（SubCategory） | 91 |
| 语法点（GrammarPoint，核心节点） | 1222 |
| PREREQUISITE 关系（保守类内推导） | ~953 |
| RELATED_BY_KEYWORD 关系（可选辅助） | ~5068 |

---

## 本体设计

### 实体层级

```
Level (A1~C2)
  └── SuperCategory（19 个大类，如 VERBS / CLAUSES / MODALITY）
        └── SubCategory（91 个子类，如 past simple / conditionals）
              └── GrammarPoint（1222 个语法点）
                    ├── examples（例句，存为属性）
                    ├── trigger_lemmas（触发词，存为属性）
                    └── keywords（关键词，存为属性）
```

### 关系类型

| 关系 | 方向 | 类型 | 说明 |
|------|------|------|------|
| `LEVEL_ORDER` | Level → Level | 直接 | 等级递进 A1→A2→…→C2 |
| `CATEGORY_CONTAINS` | SuperCategory → SubCategory | 直接 | 大类包含子类 |
| `AT_LEVEL` | GrammarPoint → Level | 直接 | 语法点所属等级 |
| `IN_SUPER_CATEGORY` | GrammarPoint → SuperCategory | 直接 | 所属大类 |
| `IN_SUB_CATEGORY` | GrammarPoint → SubCategory | 直接 | 所属子类 |
| `PREREQUISITE` | GrammarPoint → GrammarPoint | 推导 | 同 SubCategory 内按 llm_score 顺序建立相邻依赖 |
| `RELATED_BY_KEYWORD` | GrammarPoint → GrammarPoint | 可选推导 | 共享 ≥2 个关键词的辅助关联 |

### PREREQUISITE 推导规则

规则保守且可解释：**同一 SubCategory 内，按等级顺序和 llm_score 顺序，在相邻语法点之间建立 PREREQUISITE 边**。不跨子类强行补边，不依赖 LLM 直接写入核心图谱。

- `intra_level`：同等级内、同子类内相邻节点
- `cross_level`：跨等级、同子类内相邻节点

孤立节点（所在子类仅 1 个节点）属于正常情况，不人为补边。

---

## 学习路径生成

`step7_learning_paths.py` 支持以下维度的路径切片：

| 路径类型 | 示例 |
|----------|------|
| 全量路径 | `full_a1_c2` — A1 到 C2 完整路径 |
| 单等级路径 | `level_a1` / `level_b2` / … |
| 等级区间路径 | `range_a1_a2` / `range_b1_c1` / … |
| 主题路径 | `tenses` / `modality` / `clauses` / `pronouns` / … |

**路径排序规则**（优先级从高到低）：

1. CEFR 等级（A1 < A2 < … < C2）
2. 等级内按 `llm_score` 升序（与 `A1_C2_sorted.json` 权威顺序一致）
3. llm_score 相同时按拓扑排序（保证类内 PREREQUISITE 顺序）
4. 最后按 `egp_id` 字典序兜底

生成的路径中每个语法点包含 `order`（序号）和 `prerequisites`（前置依赖 egp_id 列表）。

---

## 输出文件

```
output/
├── A1_C2_sorted.json           # 权威有序语法点数组（step0 生成）
├── egp_kg.json                 # 完整图谱 JSON（节点 + 边）
├── egp_kg_a1.json              # 按等级分片（×6，a1~c2）
├── egp_kg_a2.json
├── egp_kg_b1.json
├── egp_kg_b2.json
├── egp_kg_c1.json
├── egp_kg_c2.json
├── nodes.csv                   # 节点表（可导入 Neo4j / 数据库）
├── edges.csv                   # 关系表
├── import_neo4j.cypher         # Neo4j 批量导入脚本
├── learning_path.json          # 层级结构化学习路径
│
├── path_full_a1_c2.json        # 完整 A1→C2 路径（step7 生成）
├── path_level_a1.json          # 单等级路径（×6）
├── path_tenses.json            # 时态主题路径
├── path_modality.json          # 情态动词主题路径
├── path_clauses.json           # 从句主题路径
├── ...                         # 其他主题路径
│
└── paths/                      # 路径集合（含索引）
    ├── index.json
    └── *.json
```

---

## 交互式探索器（Step 10）

```bash
python step10_path_explorer.py [--port 8080]
```

访问 `http://localhost:5002`，支持：

- 按等级、大类、关键词搜索和筛选 1222 个语法点
- 选择一个或多个目标语法点
- 实时计算「前置依赖闭包 + 拓扑排序」学习序列
- 按等级分组展示，点击节点查看详情

> 注意：探索器计算的是**前置依赖闭包 + 拓扑排序**的学习序列，不是图论意义上的最短路径。

---

## LLM 跨类标注（可选，Step 8）

如需辅助探索跨子类的前置依赖候选，可运行 Step 8。标注结果存为 `cross_prerequisites.json`，通过 Step 9 叠加到图谱中，**不直接写入核心图谱事实**。

配置 API Key：

```yaml
# config.yaml
api:
  base_url: "https://api.moonshot.cn/v1"
  api_key: "YOUR_API_KEY_HERE"
  model: "moonshot-v1-128k"
```

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 图谱构建 | NetworkX（有向图） |
| 静态可视化 | PyVis |
| 交互式 Web | Flask + 纯 HTML/CSS |
| 数据处理 | Pandas |
| LLM 标注 | OpenAI SDK（兼容 Kimi/Moonshot） |

---

## 设计约束

- **所有核心关系必须可解释**，可追溯到明确规则或数据来源，不依赖 LLM 自动写入
- **可复现性**：相同输入数据重复构建，核心图谱结构与路径顺序完全一致
- **不强行消除孤立节点**：孤立语法点（所在子类只有 1 个节点）不人为补边
- **RELATED_BY_KEYWORD 仅供探索**，不参与学习路径核心排序计算
