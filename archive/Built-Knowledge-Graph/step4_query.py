"""
Step 4: 查询知识图谱

针对 EGP 语法图谱的典型查询场景：
  1. 学习路径查询 — 某个等级应该学什么？
  2. 语法点详情 — 查看某个语法点的全部关联
  3. 前置依赖链 — 某个语法点的学习前置条件
  4. 关联推荐 — 与某个语法点最相关的其他语法点
  5. 子类纵览 — 某个子类下所有语法点的等级分布
  6. 跨类关联 — 跨大类的关键词关联发现
  7. 学习路径生成 — 从 A1 到 C2 的完整路径
"""

from collections import defaultdict

import networkx as nx

from step1_ontology import LEVELS
from step3_build_graph import build_knowledge_graph


def query_level_overview(G: nx.DiGraph, level: str):
    """查询 1: 某个等级的学习概览"""
    level_id = f"level:{level}"
    if level_id not in G:
        print(f"  等级 '{level}' 不存在")
        return

    # 找到所有该等级的语法点
    gps = []
    for src, tgt, data in G.edges(data=True):
        if tgt == level_id and data.get("relation") == "AT_LEVEL":
            gps.append(src)

    # 按大类分组
    by_super = defaultdict(list)
    for gp_id in gps:
        gp_data = G.nodes[gp_id]
        by_super[gp_data.get("super_category", "")].append(gp_data)

    print(f"\n  {level} 等级概览: 共 {len(gps)} 个语法点")
    print(f"  涉及 {len(by_super)} 个语法大类:\n")
    for cat, points in sorted(by_super.items(), key=lambda x: -len(x[1])):
        print(f"    {cat} ({len(points)} 个):")
        for gp in points[:3]:
            print(f"      • {gp.get('egp_id', '')} {gp.get('name_zh', '')}")
        if len(points) > 3:
            print(f"      ... 还有 {len(points)-3} 个")


def query_grammar_point_detail(G: nx.DiGraph, egp_id: str):
    """查询 2: 语法点详情"""
    gp_id = f"gp:{egp_id}"
    if gp_id not in G:
        print(f"  语法点 '{egp_id}' 不存在")
        return

    gp = G.nodes[gp_id]
    print(f"\n  【{gp.get('egp_id', '')}】{gp.get('name_zh', '')}")
    print(f"  Level: {gp.get('level', '')}")
    print(f"  Category: {gp.get('super_category', '')} > {gp.get('sub_category', '')}")
    print(f"  Guideword: {gp.get('guideword', '')}")
    print(f"  CanDo: {gp.get('can_do', '')}")

    # 按关系类型分组出边
    by_rel = defaultdict(list)
    for _, tgt, data in G.out_edges(gp_id, data=True):
        by_rel[data.get("relation", "")].append(tgt)

    if "HAS_EXAMPLE" in by_rel:
        print(f"\n  例句 ({len(by_rel['HAS_EXAMPLE'])}):")
        for ex_id in by_rel["HAS_EXAMPLE"][:3]:
            print(f"    • {G.nodes[ex_id].get('sentence', '')[:80]}")

    if "HAS_TRIGGER" in by_rel:
        triggers = [G.nodes[t].get("name", "") for t in by_rel["HAS_TRIGGER"]]
        print(f"\n  触发词: {', '.join(triggers)}")

    if "HAS_KEYWORD" in by_rel:
        kws = [G.nodes[k].get("name", "") for k in by_rel["HAS_KEYWORD"]]
        print(f"  关键词: {', '.join(kws)}")

    if "PREREQUISITE" in by_rel:
        print(f"\n  后续语法点 (PREREQUISITE →):")
        for next_id in by_rel["PREREQUISITE"]:
            nd = G.nodes[next_id]
            print(f"    → [{nd.get('level', '')}] {nd.get('egp_id', '')} {nd.get('name_zh', '')}")

    # 入边中的 PREREQUISITE（谁是我的前置？）
    prereqs = [
        src for src, _, d in G.in_edges(gp_id, data=True)
        if d.get("relation") == "PREREQUISITE"
    ]
    if prereqs:
        print(f"\n  前置条件 (← PREREQUISITE):")
        for pre_id in prereqs:
            nd = G.nodes[pre_id]
            print(f"    ← [{nd.get('level', '')}] {nd.get('egp_id', '')} {nd.get('name_zh', '')}")

    if "RELATED_BY_KEYWORD" in by_rel:
        print(f"\n  关键词关联 ({len(by_rel['RELATED_BY_KEYWORD'])} 个):")
        for rel_id in by_rel["RELATED_BY_KEYWORD"][:5]:
            nd = G.nodes[rel_id]
            edge = G.edges[gp_id, rel_id]
            shared = edge.get("shared_keywords", 0)
            print(f"    ~ [{nd.get('level', '')}] {nd.get('egp_id', '')} {nd.get('name_zh', '')} (共享 {shared} 个关键词)")


def query_prerequisite_chain(G: nx.DiGraph, egp_id: str):
    """查询 3: 前置依赖链（向前追溯到最底层）"""
    gp_id = f"gp:{egp_id}"
    if gp_id not in G:
        print(f"  语法点 '{egp_id}' 不存在")
        return

    gp = G.nodes[gp_id]
    print(f"\n  【{egp_id}】{gp.get('name_zh', '')} 的前置依赖链:")

    # 向上追溯
    chain = []
    visited = {gp_id}
    current = gp_id

    while True:
        prereqs = [
            src for src, _, d in G.in_edges(current, data=True)
            if d.get("relation") == "PREREQUISITE" and src not in visited
        ]
        if not prereqs:
            break
        pre = prereqs[0]
        chain.append(pre)
        visited.add(pre)
        current = pre

    chain.reverse()
    chain.append(gp_id)

    # 向下追溯
    current = gp_id
    while True:
        nexts = [
            tgt for _, tgt, d in G.out_edges(current, data=True)
            if d.get("relation") == "PREREQUISITE" and tgt not in visited
        ]
        if not nexts:
            break
        nxt = nexts[0]
        chain.append(nxt)
        visited.add(nxt)
        current = nxt

    print(f"  完整路径 (长度 {len(chain)}):\n")
    for i, node_id in enumerate(chain):
        nd = G.nodes[node_id]
        marker = "  ★ " if node_id == gp_id else "    "
        arrow = " → " if i < len(chain) - 1 else ""
        print(f"  {marker}[{nd.get('level', '')}] {nd.get('egp_id', '')} {nd.get('name_zh', '')}{arrow}")


def query_subcategory_overview(G: nx.DiGraph, super_cat: str, sub_cat: str):
    """查询 4: 子类纵览 — 某个子类下所有语法点的等级分布"""
    sub_id = f"sub:{super_cat}::{sub_cat}"
    if sub_id not in G:
        print(f"  子类 '{super_cat}::{sub_cat}' 不存在")
        return

    gps = []
    for src, tgt, data in G.edges(data=True):
        if tgt == sub_id and data.get("relation") == "IN_SUB_CATEGORY":
            gps.append(src)

    level_rank = {lvl: i for i, lvl in enumerate(LEVELS)}
    gp_data_list = [(gp_id, G.nodes[gp_id]) for gp_id in gps]
    gp_data_list.sort(key=lambda x: level_rank.get(x[1].get("level", ""), 99))

    print(f"\n  {super_cat} > {sub_cat}: 共 {len(gps)} 个语法点\n")

    by_level = defaultdict(list)
    for gp_id, gd in gp_data_list:
        by_level[gd.get("level", "")].append((gp_id, gd))

    for lvl in LEVELS:
        if lvl not in by_level:
            continue
        items = by_level[lvl]
        print(f"  [{lvl}] ({len(items)} 个):")
        for gp_id, gd in items:
            # 检查是否有前置依赖
            prereqs = [
                G.nodes[s].get("egp_id", "")
                for s, _, d in G.in_edges(gp_id, data=True)
                if d.get("relation") == "PREREQUISITE"
            ]
            pre_str = f" ← 依赖: {','.join(prereqs)}" if prereqs else ""
            print(f"    • {gd.get('egp_id', '')} {gd.get('name_zh', '')}{pre_str}")


def query_cross_category_relations(G: nx.DiGraph, top_n: int = 15):
    """查询 5: 跨大类的关键词关联"""
    print(f"\n  跨大类的关键词关联 (Top {top_n}):\n")

    cross_relations = []
    for src, tgt, data in G.edges(data=True):
        if data.get("relation") != "RELATED_BY_KEYWORD":
            continue
        src_d = G.nodes[src]
        tgt_d = G.nodes[tgt]
        if src_d.get("super_category") != tgt_d.get("super_category"):
            cross_relations.append((
                data.get("shared_keywords", 0),
                src_d, tgt_d,
            ))

    cross_relations.sort(key=lambda x: -x[0])
    for shared, a, b in cross_relations[:top_n]:
        print(f"    [{a.get('level','')}:{a.get('super_category','')}] {a.get('name_zh','')[:20]}")
        print(f"      ↔ (共享 {shared} 个关键词)")
        print(f"    [{b.get('level','')}:{b.get('super_category','')}] {b.get('name_zh','')[:20]}")
        print()


def query_learning_path(G: nx.DiGraph, from_level: str = "A1", to_level: str = "C2"):
    """
    查询 6: 生成学习路径统计
    统计从某等级到某等级需要掌握的语法点数和分布
    """
    level_rank = {lvl: i for i, lvl in enumerate(LEVELS)}
    from_rank = level_rank.get(from_level, 0)
    to_rank = level_rank.get(to_level, 5)

    target_levels = [lvl for lvl in LEVELS if from_rank <= level_rank[lvl] <= to_rank]

    print(f"\n  学习路径: {from_level} → {to_level}")
    print(f"  覆盖等级: {' → '.join(target_levels)}\n")

    total = 0
    for lvl in target_levels:
        level_id = f"level:{lvl}"
        gps = [
            src for src, tgt, d in G.edges(data=True)
            if tgt == level_id and d.get("relation") == "AT_LEVEL"
        ]
        total += len(gps)

        # 按大类统计
        by_super = defaultdict(int)
        for gp_id in gps:
            by_super[G.nodes[gp_id].get("super_category", "")] += 1

        top_cats = sorted(by_super.items(), key=lambda x: -x[1])[:5]
        cat_str = ", ".join(f"{c}({n})" for c, n in top_cats)
        print(f"  [{lvl}] {len(gps):3d} 个语法点 | 主要: {cat_str}")

    print(f"\n  总计: {total} 个语法点需要掌握")

    # 统计有前置依赖的语法点
    prereq_edges = sum(
        1 for _, _, d in G.edges(data=True)
        if d.get("relation") == "PREREQUISITE"
    )
    print(f"  前置依赖关系: {prereq_edges} 条")


def run_all_queries(G: nx.DiGraph):
    """运行所有查询示例"""
    print("=" * 60)
    print("  EGP 语法知识图谱 — 查询示例")
    print("=" * 60)

    # 查询 1
    print("\n" + "─" * 50)
    print("  查询 1: A1 等级学习概览")
    print("─" * 50)
    query_level_overview(G, "A1")

    # 查询 2
    print("\n" + "─" * 50)
    print("  查询 2: 语法点详情 — GG-A1-001")
    print("─" * 50)
    query_grammar_point_detail(G, "GG-A1-001")

    # 查询 3
    print("\n" + "─" * 50)
    print("  查询 3: 前置依赖链 — GG-B2-001")
    print("─" * 50)
    query_prerequisite_chain(G, "GG-B2-001")

    # 查询 4
    print("\n" + "─" * 50)
    print("  查询 4: 子类纵览 — PAST > past simple")
    print("─" * 50)
    query_subcategory_overview(G, "PAST", "past simple")

    # 查询 5
    print("\n" + "─" * 50)
    print("  查询 5: 跨大类的关键词关联")
    print("─" * 50)
    query_cross_category_relations(G, top_n=10)

    # 查询 6
    print("\n" + "─" * 50)
    print("  查询 6: 学习路径 A1 → C2")
    print("─" * 50)
    query_learning_path(G, "A1", "C2")


if __name__ == "__main__":
    print("  构建图谱中...\n")
    G = build_knowledge_graph()
    print()
    run_all_queries(G)
