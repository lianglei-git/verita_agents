"""
EGP 英语语法知识图谱 — 主入口

执行完整构建流程并输出所有交付物。

用法:
  python main.py              # 完整构建（不含可选关键词关系）
  python main.py --with-kw    # 包含 RELATED_BY_KEYWORD 辅助关系
  python main.py --no-viz     # 跳过可视化
"""

import argparse
import os
import sys

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def run(with_keyword_relations: bool = False, skip_viz: bool = False):
    # ── Step 0: 合并各等级数据 ─────────────────────────────────
    print("\n" + "=" * 60)
    print("  [Step 0] 合并各等级 full_sort_latest.json")
    print("=" * 60)
    from step0_build_sorted_array import main as step0_main
    step0_main()

    # ── Step 2: 解析数据 ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("  [Step 2] 解析语法点数据")
    print("=" * 60)
    from step2_parse_egp import load_grammar_points, print_parse_stats
    data = load_grammar_points()
    print_parse_stats(data)

    # ── Step 3: 构建图谱 ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("  [Step 3] 构建知识图谱")
    print("=" * 60)
    from step3_build_graph import build_knowledge_graph, validate_graph
    G = build_knowledge_graph(data, include_keyword_relations=with_keyword_relations)

    from collections import Counter
    rel_counts = Counter(d.get("relation") for _, _, d in G.edges(data=True))
    print(f"\n  图谱节点总数: {G.number_of_nodes()}")
    print(f"  图谱关系总数: {G.number_of_edges()}")
    print("\n  关系类型分布:")
    for rel, cnt in rel_counts.most_common():
        print(f"    {rel:30s}: {cnt}")

    validate_graph(G)

    # ── Step 5: 导出数据 ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("  [Step 5] 导出数据")
    print("=" * 60)
    from step5_export import export_json, export_level_slices, export_csv, export_learning_path_json
    export_json(G)
    export_level_slices(G)
    export_csv(G)
    export_learning_path_json(G)

    # ── Step 7: 生成学习路径 ────────────────────────────────────
    print("\n" + "=" * 60)
    print("  [Step 7] 生成学习路径")
    print("=" * 60)
    from step7_learning_paths import generate_preset_paths, export_all_paths
    paths = generate_preset_paths(G)
    export_all_paths(paths)
    print(f"  已生成 {len(paths)} 条学习路径")

    # ── Step 6: 可视化（可跳过）────────────────────────────────
    if not skip_viz:
        print("\n" + "=" * 60)
        print("  [Step 6] 生成可视化")
        print("=" * 60)
        try:
            from step6_visualize import (
                visualize_skeleton,
                visualize_level_subgraph,
                visualize_prerequisites,
            )
            visualize_skeleton(G)
            for level in ["A1", "B1", "C1"]:
                visualize_level_subgraph(G, level)
            visualize_prerequisites(G)
            print("  可视化完成，查看 output/*.html")
        except ImportError as e:
            print(f"  [跳过] 可视化依赖未安装: {e}")
    else:
        print("\n  [跳过] 可视化 (--no-viz)")

    # ── 完成 ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  构建完成")
    print("=" * 60)
    print(f"\n  输出目录: {OUTPUT_DIR}")
    print("\n  核心输出文件:")
    for name in [
        "A1_C2_sorted.json",
        "egp_kg.json",
        "nodes.csv",
        "edges.csv",
        "learning_path.json",
    ]:
        path = os.path.join(OUTPUT_DIR, name)
        size = f"{os.path.getsize(path) // 1024} KB" if os.path.exists(path) else "未生成"
        print(f"    {name:30s} {size}")

    print("\n  交互式探索器:")
    print("    python step10_path_explorer.py")
    print("    打开 http://localhost:5002\n")

    return G


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EGP 语法知识图谱 — 完整构建")
    parser.add_argument(
        "--with-kw", action="store_true",
        help="包含 RELATED_BY_KEYWORD 辅助关联（默认关闭）"
    )
    parser.add_argument(
        "--no-viz", action="store_true",
        help="跳过可视化生成"
    )
    args = parser.parse_args()

    run(with_keyword_relations=args.with_kw, skip_viz=args.no_viz)
