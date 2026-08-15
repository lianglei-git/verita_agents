"""
Step 1: 本体定义 (Ontology)

基于 EGP 数据结构设计知识图谱的模式层。

层级结构：
  Level (A1~C2)
    └── SuperCategory (19 个语法大类)
          └── SubCategory (91 个语法子类)
                └── GrammarPoint (1222 个语法点)
                      ├── Example (例句)
                      ├── TriggerLemma (触发词)
                      └── Keyword (关键词)

推导关系：
  GrammarPoint --PREREQUISITE--> GrammarPoint
      同一 SubCategory 内，低 level → 高 level
  GrammarPoint --RELATED_BY_KEYWORD--> GrammarPoint
      共享 ≥2 个 keyword 的语法点
"""

# ============================================================
# CEFR 等级定义
# ============================================================

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

LEVEL_INFO = {
    "A1": {"name_zh": "入门", "description": "Breakthrough / Beginner"},
    "A2": {"name_zh": "基础", "description": "Waystage / Elementary"},
    "B1": {"name_zh": "中级", "description": "Threshold / Intermediate"},
    "B2": {"name_zh": "中高级", "description": "Vantage / Upper Intermediate"},
    "C1": {"name_zh": "高级", "description": "Effective Operational Proficiency / Advanced"},
    "C2": {"name_zh": "精通", "description": "Mastery / Proficiency"},
}

# ============================================================
# 实体类型定义
# ============================================================

ENTITY_TYPES = {
    "Level": {
        "description": "CEFR 语言能力等级",
        "source": "EGP level 字段",
        "count": 6,
    },
    "SuperCategory": {
        "description": "语法大类（如 VERBS, CLAUSES, MODALITY）",
        "source": "EGP category 字段中 SuperCategory 部分",
        "count": 19,
    },
    "SubCategory": {
        "description": "语法子类（如 past simple, conditionals）",
        "source": "EGP category 字段中 SubCategory 部分",
        "count": 91,
    },
    "GrammarPoint": {
        "description": "具体语法点（核心节点）",
        "source": "EGP 每一行数据",
        "count": 1222,
    },
    "Example": {
        "description": "示例句子",
        "source": "EGP examples 字段拆分",
    },
    "TriggerLemma": {
        "description": "触发词/词元（标志性词汇形式）",
        "source": "EGP trigger_lemmas 字段拆分",
    },
    "Keyword": {
        "description": "关键词标签",
        "source": "EGP keywords 字段拆分",
    },
}

# ============================================================
# 关系类型定义
# ============================================================

RELATIONSHIP_TYPES = {
    "LEVEL_ORDER": {
        "from_type": "Level",
        "to_type": "Level",
        "description": "CEFR 等级递进 (A1→A2→B1→B2→C1→C2)",
        "inferred": False,
    },
    "CATEGORY_CONTAINS": {
        "from_type": "SuperCategory",
        "to_type": "SubCategory",
        "description": "语法大类包含子类",
        "inferred": False,
    },
    "AT_LEVEL": {
        "from_type": "GrammarPoint",
        "to_type": "Level",
        "description": "语法点的 CEFR 等级",
        "inferred": False,
    },
    "IN_SUPER_CATEGORY": {
        "from_type": "GrammarPoint",
        "to_type": "SuperCategory",
        "description": "语法点所属大类",
        "inferred": False,
    },
    "IN_SUB_CATEGORY": {
        "from_type": "GrammarPoint",
        "to_type": "SubCategory",
        "description": "语法点所属子类",
        "inferred": False,
    },
    "HAS_EXAMPLE": {
        "from_type": "GrammarPoint",
        "to_type": "Example",
        "description": "语法点的示例句子",
        "inferred": False,
    },
    "HAS_TRIGGER": {
        "from_type": "GrammarPoint",
        "to_type": "TriggerLemma",
        "description": "语法点的触发词",
        "inferred": False,
    },
    "HAS_KEYWORD": {
        "from_type": "GrammarPoint",
        "to_type": "Keyword",
        "description": "语法点的关键词标签",
        "inferred": False,
    },
    "PREREQUISITE": {
        "from_type": "GrammarPoint",
        "to_type": "GrammarPoint",
        "description": "学习前置依赖（同 SubCategory 内低级 → 高级）",
        "inferred": True,
    },
    "RELATED_BY_KEYWORD": {
        "from_type": "GrammarPoint",
        "to_type": "GrammarPoint",
        "description": "关键词关联（共享 ≥2 个 keyword）",
        "inferred": True,
    },
}


def print_ontology():
    """打印本体定义概览"""
    print("=" * 60)
    print("  EGP 英语语法知识图谱 — 本体定义")
    print("=" * 60)

    print("\n  CEFR 等级:")
    for lvl in LEVELS:
        info = LEVEL_INFO[lvl]
        print(f"    {lvl} | {info['name_zh']:4s} | {info['description']}")

    print(f"\n  实体类型 ({len(ENTITY_TYPES)}):")
    print("  " + "-" * 50)
    for name, info in ENTITY_TYPES.items():
        cnt = info.get("count", "~N")
        print(f"    {name:20s} | {info['description']} ({cnt})")

    print(f"\n  关系类型 ({len(RELATIONSHIP_TYPES)}):")
    print("  " + "-" * 50)
    for name, info in RELATIONSHIP_TYPES.items():
        tag = " [推导]" if info["inferred"] else ""
        print(f"    [{info['from_type']}] --{name}--> [{info['to_type']}]{tag}")
        print(f"      {info['description']}")


if __name__ == "__main__":
    print_ontology()
