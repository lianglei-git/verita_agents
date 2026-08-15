"""
Step 3: 构建知识图谱

两个阶段：
  Phase A — 直接关系：从 EGP 数据中直接提取
  Phase B — 保守推导：仅基于明确规则推导 PREREQUISITE

PREREQUISITE 推导规则（保守版，来自需求文档 §7.3）：
  同一 SubCategory 内，按源数据顺序（llm_score 升序，即 A1_C2_sorted.json 的原始顺序）
  建立相邻节点的 PREREQUISITE 关系。

不再推导：
  - 横向跨子类依赖（原 step8_llm_horizontal 产物）
  - LLM 标注跨类依赖（原 step8_llm_annotate 产物）

可选增强（默认关闭）：
  RELATED_BY_KEYWORD：共享 ≥2 个 keyword 的语法点之间建立辅助关联。
  仅用于探索/可视化，不参与学习路径核心计算。
  调用 build_knowledge_graph(include_keyword_relations=True) 启用。
"""

from collections import defaultdict

import networkx as nx

from step1_ontology import LEVELS, LEVEL_INFO
from step2_parse_egp import GrammarPointData, load_grammar_points


def build_knowledge_graph(
    data: list = None,
    include_keyword_relations: bool = False,
) -> nx.DiGraph:
    """
    构建 EGP 语法知识图谱。

    Args:
        data: GrammarPointData 列表。如不提供则自动从 A1_C2_sorted.json 加载。
        include_keyword_relations: 是否推导 RELATED_BY_KEYWORD（默认关闭）。

    Returns:
        nx.DiGraph
    """
    if data is None:
        data = load_grammar_points()

    G = nx.DiGraph()

    # ── Phase A: 直接关系 ─────────────────────────────────

    _build_level_nodes(G)
    _build_category_nodes(G, data)
    _build_grammar_point_nodes(G, data)

    # ── Phase B: 保守推导 ─────────────────────────────────

    _infer_intra_subcategory_prerequisites(G, data)

    if include_keyword_relations:
        _infer_keyword_relations(G, data)

    return G


# ─────────────────────────────────────────────────────────────
# Phase A 构建函数
# ─────────────────────────────────────────────────────────────

def _build_level_nodes(G: nx.DiGraph):
    for i, lvl in enumerate(LEVELS):
        info = LEVEL_INFO[lvl]
        G.add_node(f"level:{lvl}", **{
            "type": "Level",
            "name": lvl,
            "name_zh": info["name_zh"],
            "description": info["description"],
            "order": i,
        })
    for i in range(len(LEVELS) - 1):
        G.add_edge(
            f"level:{LEVELS[i]}", f"level:{LEVELS[i+1]}",
            relation="LEVEL_ORDER",
        )


def _build_category_nodes(G: nx.DiGraph, data: list):
    seen_super = set()
    seen_sub = set()
    seen_link = set()

    for gp in data:
        sc_id = f"super:{gp.super_category}"
        sub_id = f"sub:{gp.super_category}::{gp.sub_category}"

        if sc_id not in seen_super:
            G.add_node(sc_id, type="SuperCategory", name=gp.super_category)
            seen_super.add(sc_id)

        if sub_id not in seen_sub:
            G.add_node(sub_id, type="SubCategory", name=gp.sub_category,
                       super_category=gp.super_category)
            seen_sub.add(sub_id)

        link = (sc_id, sub_id)
        if link not in seen_link:
            G.add_edge(sc_id, sub_id, relation="CATEGORY_CONTAINS")
            seen_link.add(link)


def _build_grammar_point_nodes(G: nx.DiGraph, data: list):
    for gp in data:
        gp_id = f"gp:{gp.egp_id}"

        G.add_node(gp_id, **{
            "type": "GrammarPoint",
            "name": gp.name_zh or gp.guideword,
            "egp_id": gp.egp_id,
            "name_zh": gp.name_zh,
            "guideword": gp.guideword,
            "can_do": gp.can_do,
            "level": gp.level,
            "super_category": gp.super_category,
            "sub_category": gp.sub_category,
            "llm_score": gp.llm_score,
            "examples": gp.examples,
            "trigger_lemmas": gp.trigger_lemmas,
            "keywords": gp.keywords,
            "chinese_doc": gp.chinese_doc,
            "core_rules": gp.core_rules,
            "common_errors": gp.common_errors,
        })

        G.add_edge(gp_id, f"level:{gp.level}", relation="AT_LEVEL")
        G.add_edge(gp_id, f"super:{gp.super_category}", relation="IN_SUPER_CATEGORY")
        G.add_edge(gp_id, f"sub:{gp.super_category}::{gp.sub_category}", relation="IN_SUB_CATEGORY")


# ─────────────────────────────────────────────────────────────
# Phase B 推导函数
# ─────────────────────────────────────────────────────────────

def _infer_intra_subcategory_prerequisites(G: nx.DiGraph, data: list):
    """
    推导 PREREQUISITE 关系（保守版）。

    规则：同一 SubCategory 内，按源数据顺序（即 A1_C2_sorted.json 的原始下标，
    保留了 llm_score 升序）建立相邻节点的 PREREQUISITE 边。

    不强行串联不同 SubCategory，不为了"消除孤立节点"而补边。
    """
    level_rank = {lvl: i for i, lvl in enumerate(LEVELS)}

    groups = defaultdict(list)
    # data 已按 A1_C2_sorted.json 顺序排列（等级升序 + 类内 llm_score 升序）
    for idx, gp in enumerate(data):
        key = (gp.super_category, gp.sub_category)
        groups[key].append((idx, gp))

    intra_count = 0
    cross_count = 0

    for key, indexed_gps in groups.items():
        if len(indexed_gps) < 2:
            continue

        # 先按等级排序，等级内按源数据下标（即 llm_score 顺序）
        sorted_gps = sorted(
            indexed_gps,
            key=lambda x: (level_rank.get(x[1].level, 99), x[0])
        )

        for i in range(len(sorted_gps) - 1):
            curr_idx, curr = sorted_gps[i]
            next_idx, next_gp = sorted_gps[i + 1]

            same_level = curr.level == next_gp.level
            ptype = "intra_level" if same_level else "cross_level"

            G.add_edge(
                f"gp:{curr.egp_id}",
                f"gp:{next_gp.egp_id}",
                relation="PREREQUISITE",
                prerequisite_type=ptype,
                from_level=curr.level,
                to_level=next_gp.level,
            )

            if same_level:
                intra_count += 1
            else:
                cross_count += 1

    total = intra_count + cross_count
    print(f"    推导 PREREQUISITE (类内): {total} 条")
    print(f"      intra_level (同级): {intra_count}")
    print(f"      cross_level (跨级): {cross_count}")

    # 统计不在任何 PREREQUISITE 链中的孤立语法点（仅报告，不补边）
    gp_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "GrammarPoint"]
    in_prereq = set()
    for u, v, d in G.edges(data=True):
        if d.get("relation") == "PREREQUISITE":
            in_prereq.add(u)
            in_prereq.add(v)
    isolated = [n for n in gp_nodes if n not in in_prereq]
    if isolated:
        print(f"    孤立语法点 (无 PREREQUISITE 连接): {len(isolated)} 个")
        print(f"      这些语法点所在子类只有 1 个节点，属于正常情况")


def _infer_keyword_relations(G: nx.DiGraph, data: list, min_shared: int = 2):
    """
    [可选] 推导 RELATED_BY_KEYWORD 辅助关联。
    共享 ≥ min_shared 个 keyword 的语法点之间建立辅助关联边。
    此关系仅用于相似浏览，不参与学习路径计算。
    """
    print("    推导 RELATED_BY_KEYWORD (可选)...", end="", flush=True)

    kw_to_gps = defaultdict(set)
    for gp in data:
        for kw in gp.keywords:
            kw_clean = kw.strip().lower()
            if kw_clean:
                kw_to_gps[kw_clean].add(gp.egp_id)

    # 过滤超高频关键词（过于通用，无区分价值）
    kw_to_gps = {k: v for k, v in kw_to_gps.items() if len(v) <= 50}

    pair_shared = defaultdict(int)
    for kw, gp_ids in kw_to_gps.items():
        if len(gp_ids) < 2:
            continue
        sorted_ids = sorted(gp_ids)
        for i in range(len(sorted_ids)):
            for j in range(i + 1, len(sorted_ids)):
                pair_shared[(sorted_ids[i], sorted_ids[j])] += 1

    added = 0
    for (a, b), shared in pair_shared.items():
        if shared < min_shared:
            continue
        u, v = f"gp:{a}", f"gp:{b}"
        if not G.has_edge(u, v):
            G.add_edge(u, v, relation="RELATED_BY_KEYWORD", shared_keywords=shared)
            added += 1

    print(f" 完成 ({added} 条)")


# ─────────────────────────────────────────────────────────────
# 图谱验证
# ─────────────────────────────────────────────────────────────

def validate_graph(G: nx.DiGraph) -> bool:
    """
    验证图谱基本完整性。
    不要求 0 孤立节点——这是正常的（单节点子类无法形成链）。
    """
    print("\n  ── 图谱验证 ──")
    all_passed = True

    gp_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "GrammarPoint"]
    prereq_edges = [(u, v) for u, v, d in G.edges(data=True)
                    if d.get("relation") == "PREREQUISITE"]

    print(f"  语法点总数: {len(gp_nodes)}")
    print(f"  PREREQUISITE 关系数: {len(prereq_edges)}")

    # 检查 DAG（无环）
    prereq_only = nx.DiGraph()
    for u, v in prereq_edges:
        prereq_only.add_edge(u, v)

    if nx.is_directed_acyclic_graph(prereq_only):
        print(f"  ✓ PREREQUISITE 图无环（DAG）")
    else:
        cycles = list(nx.simple_cycles(prereq_only))
        print(f"  ✗ 发现 {len(cycles)} 个环路（不应存在）")
        for c in cycles[:3]:
            print(f"      {c}")
        all_passed = False

    # 检查所有语法点是否有正确的等级、分类关联
    missing_level = [n for n in gp_nodes if not G.nodes[n].get("level")]
    if missing_level:
        print(f"  ✗ {len(missing_level)} 个语法点缺少 level 字段")
        all_passed = False
    else:
        print(f"  ✓ 所有语法点均有 level 字段")

    return all_passed


if __name__ == "__main__":
    print("=" * 60)
    print("  Step 3: 构建知识图谱")
    print("=" * 60)
    print()

    data = load_grammar_points()
    print(f"  加载语法点: {len(data)} 个\n")

    G = build_knowledge_graph(data, include_keyword_relations=False)

    print(f"\n  图谱节点总数: {G.number_of_nodes()}")
    print(f"  图谱关系总数: {G.number_of_edges()}")

    from collections import Counter
    rel_counts = Counter(d.get("relation") for _, _, d in G.edges(data=True))
    print("\n  关系类型分布:")
    for rel, cnt in rel_counts.most_common():
        print(f"    {rel:30s}: {cnt}")

    validate_graph(G)
