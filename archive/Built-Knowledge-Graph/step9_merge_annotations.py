"""
Step 9: 前置依赖回溯与学习序列查询

核心功能：
  find_prerequisites_for(G, target_egp_id)
    → 回溯某个语法点的全部前置依赖，返回按 CEFR 等级排序的学习序列

  find_prerequisite_closure(G, target_egp_ids)
    → 多个目标语法点前置依赖的并集，返回统一的学习序列

注意：这里的"学习序列"是"前置依赖闭包 + 拓扑排序"的结果，
不是图论意义上的最短路径，不应对外表述为"最优"或"最短"路径。

可选：也支持加载 LLM 跨类标注（cross_prerequisites.json）叠加到图谱中，
但此功能属于探索性增强，不是核心功能。叠加后的结果可信度取决于标注质量。
"""

import json
import os
from collections import defaultdict

import networkx as nx

from step1_ontology import LEVELS
from step3_build_graph import build_knowledge_graph

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
CROSS_PREREQS_FILE = os.path.join(OUTPUT_DIR, "cross_prerequisites.json")


# ─────────────────────────────────────────────────────────────
# [可选] LLM 跨类标注合并（探索性增强）
# ─────────────────────────────────────────────────────────────

def load_cross_prerequisites() -> list:
    """
    [可选] 加载 LLM 标注的跨类依赖文件。
    若文件不存在则返回空列表，不影响核心功能。
    """
    if not os.path.exists(CROSS_PREREQS_FILE):
        return []

    with open(CROSS_PREREQS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    annotations = data.get("annotations", [])
    print(f"  [可选] 加载 LLM 跨类标注: {len(annotations)} 条")
    return annotations


def merge_cross_prerequisites(G: nx.DiGraph, annotations: list) -> int:
    """
    [可选] 将 LLM 跨类依赖叠加到图谱中。
    注意：这些关系标记为 source='llm_annotation'，可通过 include_llm=False 排除。
    """
    added = 0
    skipped = 0

    for ann in annotations:
        target_id = f"gp:{ann['egp_id']}"
        prereqs = ann.get("cross_prerequisites", [])

        if target_id not in G:
            skipped += 1
            continue

        for prereq_egp_id in prereqs:
            prereq_id = f"gp:{prereq_egp_id}"
            if prereq_id not in G:
                skipped += 1
                continue

            if G.has_edge(prereq_id, target_id):
                skipped += 1
                continue

            G.add_edge(
                prereq_id, target_id,
                relation="PREREQUISITE",
                source="llm_annotation",
                from_level=G.nodes[prereq_id].get("level", ""),
                to_level=G.nodes[target_id].get("level", ""),
            )
            added += 1

    print(f"  [可选] 叠加跨类 PREREQUISITE: +{added} 条（跳过 {skipped} 条）")
    return added


# ─────────────────────────────────────────────────────────────
# 拓扑排序（等级感知）
# ─────────────────────────────────────────────────────────────

def _topo_sort_by_level(G_sub: nx.DiGraph, G_full: nx.DiGraph) -> list:
    """
    对子图做拓扑排序，同一拓扑层内按 (level_rank, egp_id) 排序。
    保证等级低的节点在前，同等级内按 egp_id 排序。
    """
    level_rank = {lvl: i for i, lvl in enumerate(LEVELS)}

    try:
        topo = list(nx.topological_sort(G_sub))
    except nx.NetworkXUnfeasible:
        topo = list(G_sub.nodes())

    return sorted(topo, key=lambda n: (
        level_rank.get(G_full.nodes[n].get("level", ""), 99),
        G_full.nodes[n].get("egp_id", ""),
    ))


# ─────────────────────────────────────────────────────────────
# 核心功能：前置依赖回溯
# ─────────────────────────────────────────────────────────────

def find_prerequisites_for(
    G: nx.DiGraph,
    target_egp_id: str,
    include_llm: bool = False,
) -> list:
    """
    回溯学习某个语法点所需的全部前置依赖（递归向前追溯）。
    返回按 CEFR 等级排序的学习序列（含目标节点本身）。

    Args:
        include_llm: 是否包含 LLM 标注的跨类依赖（默认关闭）。
    """
    target_id = f"gp:{target_egp_id}"
    if target_id not in G:
        print(f"  语法点 '{target_egp_id}' 不存在")
        return []

    required = set()
    queue = [target_id]

    while queue:
        node = queue.pop(0)
        for src, _, d in G.in_edges(node, data=True):
            if d.get("relation") != "PREREQUISITE":
                continue
            if not include_llm and d.get("source") == "llm_annotation":
                continue
            if src not in required:
                required.add(src)
                queue.append(src)

    required.add(target_id)

    sub = G.subgraph(required).copy()
    if not include_llm:
        to_remove = [(u, v) for u, v, d in sub.edges(data=True)
                     if d.get("source") == "llm_annotation"]
        sub.remove_edges_from(to_remove)

    return _topo_sort_by_level(sub, G)


def find_prerequisite_closure(
    G: nx.DiGraph,
    target_egp_ids: list,
    include_llm: bool = False,
) -> list:
    """
    学习多个目标语法点所需的前置依赖并集，返回统一的学习序列。
    （即所有目标的前置依赖闭包的并集 + 拓扑排序）
    """
    all_required = set()
    for tid in target_egp_ids:
        path = find_prerequisites_for(G, tid, include_llm=include_llm)
        all_required.update(path)

    if not all_required:
        return []

    sub = G.subgraph(all_required).copy()
    if not include_llm:
        to_remove = [(u, v) for u, v, d in sub.edges(data=True)
                     if d.get("source") == "llm_annotation"]
        sub.remove_edges_from(to_remove)

    return _topo_sort_by_level(sub, G)


# 向后兼容别名（step10 等依赖此名称）
find_shortest_path_multiple = find_prerequisite_closure


# ─────────────────────────────────────────────────────────────
# 打印与导出
# ─────────────────────────────────────────────────────────────

def print_learning_path(G: nx.DiGraph, path: list, title: str = "学习序列"):
    if not path:
        print(f"\n  {title}: 无结果")
        return

    print(f"\n  {title} ({len(path)} 个语法点):")
    print("  " + "─" * 50)

    current_level = ""
    path_set = set(path)
    for i, nid in enumerate(path):
        nd = G.nodes[nid]
        level = nd.get("level", "")
        if level != current_level:
            current_level = level
            print(f"\n    ── {level} ──")

        prereqs = [
            G.nodes[s].get("egp_id", "")
            for s, _, d in G.in_edges(nid, data=True)
            if d.get("relation") == "PREREQUISITE" and s in path_set
        ]
        pre_str = f" ← {','.join(prereqs)}" if prereqs else ""

        llm_tag = ""
        for s, _, d in G.in_edges(nid, data=True):
            if d.get("relation") == "PREREQUISITE" and d.get("source") == "llm_annotation":
                llm_tag = " [LLM]"
                break

        egp_id = nd.get("egp_id", "")
        cat = nd.get("sub_category", "")
        name = nd.get("name_zh", "")
        print(f"    #{i+1:3d} {egp_id} [{cat}] {name[:25]}{pre_str}{llm_tag}")


def export_path_json(G: nx.DiGraph, path: list, target_ids: list, filename: str):
    """导出前置依赖回溯结果为 JSON"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    path_set = set(path)
    items = []
    for i, nid in enumerate(path):
        nd = G.nodes[nid]
        prereqs = [
            G.nodes[s].get("egp_id", "")
            for s, _, d in G.in_edges(nid, data=True)
            if d.get("relation") == "PREREQUISITE" and s in path_set
        ]
        items.append({
            "order": i,
            "egp_id": nd.get("egp_id", ""),
            "name_zh": nd.get("name_zh", ""),
            "level": nd.get("level", ""),
            "super_category": nd.get("super_category", ""),
            "sub_category": nd.get("sub_category", ""),
            "prerequisites_in_path": prereqs,
            "is_target": nd.get("egp_id", "") in target_ids,
        })

    data = {
        "targets": target_ids,
        "total_steps": len(path),
        "items": items,
    }

    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  导出: {filepath}")
    return filepath


# 向后兼容别名
export_shortest_path_json = export_path_json


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────

def run_prerequisite_query():
    """演示前置依赖回溯功能"""
    print("=" * 60)
    print("  EGP 语法知识图谱 — 前置依赖回溯")
    print("=" * 60)

    print("\n  构建基础图谱...")
    G = build_knowledge_graph()

    prereq_count = sum(
        1 for _, _, d in G.edges(data=True)
        if d.get("relation") == "PREREQUISITE"
    )
    print(f"  PREREQUISITE 关系: {prereq_count} 条（类内规则推导，无 LLM 补边）")

    # 可选：叠加 LLM 跨类标注（如果文件存在）
    annotations = load_cross_prerequisites()
    if annotations:
        print("\n  发现 LLM 跨类标注文件，可选择叠加（当前演示不叠加）")
        print("  若要叠加，调用 merge_cross_prerequisites(G, annotations)")

    print("\n" + "─" * 50)
    print("  前置依赖回溯演示")
    print("─" * 50)

    # 演示 1: 单目标回溯
    target = "GG-C1-025"
    path = find_prerequisites_for(G, target, include_llm=False)
    print_learning_path(G, path, f"学习 {target} 所需的学习序列")
    if path:
        export_path_json(G, path, [target], "prereq_closure_single.json")

    # 演示 2: 多目标闭包
    targets = ["GG-B2-083", "GG-B1-261"]
    path = find_prerequisite_closure(G, targets, include_llm=False)
    print_learning_path(G, path, f"同时学习 {', '.join(targets)} 所需的学习序列")
    if path:
        export_path_json(G, path, targets, "prereq_closure_multi.json")

    print("\n  ──────────────────────────────────────────")
    print("  交互式探索器:")
    print("    python step10_path_explorer.py")
    print("    打开 http://localhost:5002")
    print("  ──────────────────────────────────────────")


if __name__ == "__main__":
    run_prerequisite_query()
