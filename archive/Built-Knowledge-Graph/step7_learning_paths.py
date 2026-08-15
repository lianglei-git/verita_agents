"""
Step 7: 灵活学习路径生成器

支持多种维度的路径切片：
  - 按等级范围: A1, A1-C2, B1-C1 ...
  - 按语法主题: 时态(Tenses), 从句(Clauses), 情态动词(Modality) ...
  - 组合过滤:   B1-B2 的时态路径, A1-A2 的从句路径 ...

每条路径包含：
  - 有序的语法点列表（按等级 + 前置依赖拓扑排序）
  - 前置依赖关系
  - 统计信息
"""

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx

from step1_ontology import LEVELS, LEVEL_INFO

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# ============================================================
# 预定义的主题路径
# ============================================================

TOPIC_PRESETS = {
    "tenses": {
        "name": "时态学习路径",
        "name_en": "Tenses Learning Path",
        "description": "覆盖 PAST, PRESENT, FUTURE 三大时态类别的完整学习路径",
        "super_categories": ["PAST", "PRESENT", "FUTURE"],
    },
    "clauses": {
        "name": "从句学习路径",
        "name_en": "Clauses Learning Path",
        "description": "覆盖所有从句类型：条件句、关系从句、比较从句、并列句等",
        "super_categories": ["CLAUSES"],
    },
    "modality": {
        "name": "情态动词学习路径",
        "name_en": "Modality Learning Path",
        "description": "覆盖 can, could, may, might, must, should, will, would 等情态表达",
        "super_categories": ["MODALITY"],
    },
    "verbs": {
        "name": "动词学习路径",
        "name_en": "Verbs Learning Path",
        "description": "覆盖动词类型、短语动词、介词动词、动词模式",
        "super_categories": ["VERBS"],
    },
    "nouns_determiners": {
        "name": "名词与限定词学习路径",
        "name_en": "Nouns & Determiners Learning Path",
        "description": "名词短语、冠词、限定词、量词",
        "super_categories": ["NOUNS", "DETERMINERS"],
    },
    "pronouns": {
        "name": "代词学习路径",
        "name_en": "Pronouns Learning Path",
        "description": "主格/宾格、反身代词、不定代词、关系代词等",
        "super_categories": ["PRONOUNS"],
    },
    "adjectives_adverbs": {
        "name": "形容词与副词学习路径",
        "name_en": "Adjectives & Adverbs Learning Path",
        "description": "比较级、最高级、副词位置、程度副词",
        "super_categories": ["ADJECTIVES", "ADVERBS"],
    },
    "sentence_structure": {
        "name": "句型结构学习路径",
        "name_en": "Sentence Structure Learning Path",
        "description": "从句、连词、被动语态、否定、疑问句、间接引语",
        "super_categories": ["CLAUSES", "CONJUNCTIONS", "PASSIVES",
                             "NEGATION", "QUESTIONS", "REPORTED SPEECH"],
    },
    "writing_skills": {
        "name": "写作技巧学习路径",
        "name_en": "Writing Skills Learning Path",
        "description": "篇章标记、焦点结构、介词运用",
        "super_categories": ["DISCOURSE MARKERS", "FOCUS", "PREPOSITIONS"],
    },
}


@dataclass
class LearningPathItem:
    """学习路径中的单个语法点"""
    egp_id: str
    name_zh: str
    guideword: str
    can_do: str
    level: str
    super_category: str
    sub_category: str
    prerequisites: list = field(default_factory=list)
    order: int = 0


@dataclass
class LearningPath:
    """一条完整的学习路径"""
    path_id: str
    name: str
    name_en: str
    description: str
    level_range: tuple
    categories: list
    items: list = field(default_factory=list)

    @property
    def total_items(self):
        return len(self.items)

    @property
    def level_distribution(self):
        dist = defaultdict(int)
        for item in self.items:
            dist[item.level] += 1
        return dict(dist)

    @property
    def category_distribution(self):
        dist = defaultdict(int)
        for item in self.items:
            dist[item.super_category] += 1
        return dict(dist)


def generate_learning_path(
    G: nx.DiGraph,
    path_id: str = "custom",
    name: str = "自定义学习路径",
    name_en: str = "Custom Learning Path",
    description: str = "",
    level_from: str = "A1",
    level_to: str = "C2",
    super_categories: list = None,
    sub_categories: list = None,
) -> LearningPath:
    """
    生成一条学习路径。

    Args:
        G: 知识图谱
        path_id: 路径唯一标识
        name: 路径名称
        name_en: 英文名称
        description: 描述
        level_from: 起始等级
        level_to: 结束等级
        super_categories: 限定大类（None = 全部）
        sub_categories: 限定子类（None = 全部）

    Returns:
        LearningPath
    """
    level_rank = {lvl: i for i, lvl in enumerate(LEVELS)}
    from_rank = level_rank.get(level_from, 0)
    to_rank = level_rank.get(level_to, 5)
    target_levels = {lvl for lvl in LEVELS if from_rank <= level_rank[lvl] <= to_rank}

    # 收集符合条件的语法点
    candidates = []
    for nid, data in G.nodes(data=True):
        if data.get("type") != "GrammarPoint":
            continue
        if data.get("level") not in target_levels:
            continue
        if super_categories and data.get("super_category") not in super_categories:
            continue
        if sub_categories and data.get("sub_category") not in sub_categories:
            continue
        candidates.append((nid, data))

    # 构建候选节点的子图用于拓扑排序
    candidate_ids = {nid for nid, _ in candidates}
    sub_g = nx.DiGraph()
    for nid, data in candidates:
        sub_g.add_node(nid, **data)

    for src, tgt, d in G.edges(data=True):
        if d.get("relation") == "PREREQUISITE":
            if src in candidate_ids and tgt in candidate_ids:
                sub_g.add_edge(src, tgt)

    # 拓扑排序（在同一拓扑层内按 level → egp_id 排序）
    try:
        topo_order = list(nx.topological_sort(sub_g))
    except nx.NetworkXUnfeasible:
        # 有环，退化为按 level + egp_id 排序
        topo_order = sorted(
            candidate_ids,
            key=lambda nid: (level_rank.get(G.nodes[nid].get("level", ""), 99),
                             G.nodes[nid].get("egp_id", ""))
        )

    # 按 level 大组内，再按 llm_score（与 A1_C2_sorted.json 权威顺序一致）排列。
    # topo_rank 作为 llm_score 相同时的次级 key，确保同 sub_category 内 PREREQUISITE 顺序。
    # 注：PREREQUISITE 边均按 llm_score 升序建立，因此用 llm_score 排序天然尊重前置依赖顺序。
    topo_rank = {nid: i for i, nid in enumerate(topo_order)}
    sorted_candidates = sorted(
        candidates,
        key=lambda x: (
            level_rank.get(x[1].get("level", ""), 99),
            x[1].get("llm_score") if x[1].get("llm_score") is not None else 99999.0,
            topo_rank.get(x[0], 99999),
            x[1].get("egp_id", ""),
        )
    )

    # 构建路径项
    items = []
    for order, (nid, data) in enumerate(sorted_candidates):
        prereqs = [
            G.nodes[s].get("egp_id", "")
            for s, _, d in G.in_edges(nid, data=True)
            if d.get("relation") == "PREREQUISITE" and s in candidate_ids
        ]
        items.append(LearningPathItem(
            egp_id=data.get("egp_id", ""),
            name_zh=data.get("name_zh", ""),
            guideword=data.get("guideword", ""),
            can_do=data.get("can_do", ""),
            level=data.get("level", ""),
            super_category=data.get("super_category", ""),
            sub_category=data.get("sub_category", ""),
            prerequisites=prereqs,
            order=order,
        ))

    path = LearningPath(
        path_id=path_id,
        name=name,
        name_en=name_en,
        description=description,
        level_range=(level_from, level_to),
        categories=super_categories or ["ALL"],
        items=items,
    )
    return path


def generate_preset_paths(G: nx.DiGraph) -> dict:
    """生成所有预设主题路径（A1-C2 全范围）"""
    paths = {}

    # 完整 A1-C2 路径
    paths["full_a1_c2"] = generate_learning_path(
        G, path_id="full_a1_c2",
        name="完整学习路径 A1→C2",
        name_en="Full Learning Path A1→C2",
        description="从零基础到精通的完整英语语法学习路径",
        level_from="A1", level_to="C2",
    )

    # 各单独等级路径
    for lvl in LEVELS:
        paths[f"level_{lvl.lower()}"] = generate_learning_path(
            G, path_id=f"level_{lvl.lower()}",
            name=f"{lvl} 等级学习路径",
            name_en=f"{lvl} Level Learning Path",
            description=f"CEFR {lvl} ({LEVEL_INFO[lvl]['name_zh']}) 等级需掌握的全部语法点",
            level_from=lvl, level_to=lvl,
        )

    # 常用等级范围
    level_ranges = [
        ("A1", "A2", "入门到基础"),
        ("A1", "B1", "入门到中级"),
        ("B1", "C1", "中级到高级"),
        ("B2", "C2", "中高级到精通"),
    ]
    for lf, lt, desc_zh in level_ranges:
        pid = f"range_{lf.lower()}_{lt.lower()}"
        paths[pid] = generate_learning_path(
            G, path_id=pid,
            name=f"学习路径 {lf}→{lt}",
            name_en=f"Learning Path {lf}→{lt}",
            description=f"从 {lf}({LEVEL_INFO[lf]['name_zh']}) 到 {lt}({LEVEL_INFO[lt]['name_zh']}) 的语法学习路径",
            level_from=lf, level_to=lt,
        )

    # 主题路径
    for topic_id, preset in TOPIC_PRESETS.items():
        paths[topic_id] = generate_learning_path(
            G, path_id=topic_id,
            name=preset["name"],
            name_en=preset["name_en"],
            description=preset["description"],
            level_from="A1", level_to="C2",
            super_categories=preset["super_categories"],
        )

    return paths


def export_path_json(path: LearningPath, filename: str = None):
    """导出单条路径为 JSON"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if filename is None:
        filename = f"path_{path.path_id}.json"

    data = {
        "path_id": path.path_id,
        "name": path.name,
        "name_en": path.name_en,
        "description": path.description,
        "level_range": list(path.level_range),
        "categories": path.categories,
        "statistics": {
            "total_items": path.total_items,
            "level_distribution": path.level_distribution,
            "category_distribution": path.category_distribution,
        },
        "items": [
            {
                "order": item.order,
                "egp_id": item.egp_id,
                "name_zh": item.name_zh,
                "guideword": item.guideword,
                "can_do": item.can_do,
                "level": item.level,
                "super_category": item.super_category,
                "sub_category": item.sub_category,
                "prerequisites": item.prerequisites,
            }
            for item in path.items
        ],
    }

    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filepath


def export_all_paths(paths: dict):
    """导出所有路径"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    paths_dir = os.path.join(OUTPUT_DIR, "paths")
    os.makedirs(paths_dir, exist_ok=True)

    # 导出每条路径
    for pid, path in paths.items():
        filepath = os.path.join(paths_dir, f"{pid}.json")
        export_path_json(path, filename=None)
        # 也存到 paths 子目录
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "path_id": path.path_id,
                "name": path.name,
                "name_en": path.name_en,
                "description": path.description,
                "level_range": list(path.level_range),
                "categories": path.categories,
                "statistics": {
                    "total_items": path.total_items,
                    "level_distribution": path.level_distribution,
                    "category_distribution": path.category_distribution,
                },
                "items": [
                    {
                        "order": item.order,
                        "egp_id": item.egp_id,
                        "name_zh": item.name_zh,
                        "guideword": item.guideword,
                        "can_do": item.can_do,
                        "level": item.level,
                        "super_category": item.super_category,
                        "sub_category": item.sub_category,
                        "prerequisites": item.prerequisites,
                    }
                    for item in path.items
                ],
            }, f, ensure_ascii=False, indent=2)

    # 导出路径索引
    index = {
        "total_paths": len(paths),
        "paths": [
            {
                "path_id": p.path_id,
                "name": p.name,
                "name_en": p.name_en,
                "description": p.description,
                "level_range": list(p.level_range),
                "total_items": p.total_items,
                "level_distribution": p.level_distribution,
            }
            for p in paths.values()
        ],
    }
    index_path = os.path.join(paths_dir, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return paths_dir


def print_path_summary(path: LearningPath):
    """打印路径摘要"""
    print(f"\n  [{path.path_id}] {path.name}")
    print(f"    {path.description}")
    print(f"    等级: {path.level_range[0]} → {path.level_range[1]} | 共 {path.total_items} 个语法点")
    lvl_dist = path.level_distribution
    dist_str = " | ".join(f"{k}:{v}" for k, v in sorted(lvl_dist.items()))
    print(f"    分布: {dist_str}")

    # 显示每个等级前 2 条作为预览
    shown_levels = set()
    for item in path.items:
        if item.level not in shown_levels and len(shown_levels) < 3:
            shown_levels.add(item.level)
            same_level = [i for i in path.items if i.level == item.level]
            print(f"    [{item.level}] 示例:")
            for s in same_level[:2]:
                pre_str = f" (依赖: {','.join(s.prerequisites)})" if s.prerequisites else ""
                print(f"      #{s.order+1} {s.egp_id} {s.name_zh[:25]}{pre_str}")
            if len(same_level) > 2:
                print(f"      ... 还有 {len(same_level)-2} 个")


def run_learning_paths(G: nx.DiGraph):
    """生成并导出所有学习路径"""
    print("=" * 60)
    print("  EGP 语法知识图谱 — 学习路径生成")
    print("=" * 60)

    paths = generate_preset_paths(G)

    # 打印摘要
    print(f"\n  共生成 {len(paths)} 条学习路径:\n")

    # 按类别分组打印
    print("  ── 完整路径 ──")
    print_path_summary(paths["full_a1_c2"])

    print("\n  ── 单等级路径 ──")
    for lvl in LEVELS:
        p = paths[f"level_{lvl.lower()}"]
        print(f"    {lvl}: {p.total_items} 个语法点")

    print("\n  ── 等级范围路径 ──")
    for pid, p in paths.items():
        if pid.startswith("range_"):
            print(f"    {p.level_range[0]}→{p.level_range[1]}: {p.total_items} 个语法点")

    print("\n  ── 主题路径 ──")
    for topic_id in TOPIC_PRESETS:
        print_path_summary(paths[topic_id])

    # 导出
    print("\n" + "─" * 50)
    print("  导出路径数据...")
    paths_dir = export_all_paths(paths)
    print(f"\n  所有路径已导出到 {paths_dir}/")
    print(f"  索引文件: {paths_dir}/index.json")

    return paths


if __name__ == "__main__":
    from step3_build_graph import build_knowledge_graph
    print("  构建图谱中...\n")
    G = build_knowledge_graph()
    print()
    run_learning_paths(G)
