"""
Step 5: 导出知识图谱数据

导出格式：
  1. JSON — 完整图谱 + 按等级分片的子图
  2. CSV  — 节点表 + 关系表（可导入 Neo4j）
  3. Neo4j Cypher — 导入脚本
"""

import json
import os
from collections import defaultdict

import networkx as nx
import pandas as pd

from step1_ontology import LEVELS

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def export_json(G: nx.DiGraph, filename: str = "egp_kg.json"):
    """导出完整图谱 JSON"""
    ensure_output_dir()

    nodes = []
    for nid, data in G.nodes(data=True):
        node = {"id": nid}
        node.update(data)
        nodes.append(node)

    edges = []
    for src, tgt, data in G.edges(data=True):
        edge = {"source": src, "target": tgt}
        edge.update(data)
        edges.append(edge)

    kg_data = {
        "metadata": {
            "title": "EGP English Grammar Knowledge Graph",
            "title_zh": "EGP 英语语法知识图谱",
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        },
        "nodes": nodes,
        "edges": edges,
    }

    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(kg_data, f, ensure_ascii=False, indent=2)
    print(f"  JSON 导出: {filepath} ({G.number_of_nodes()} 节点, {G.number_of_edges()} 边)")
    return filepath


def export_level_slices(G: nx.DiGraph):
    """
    按等级导出子图 JSON，方便前端按需加载。
    每个等级一个文件，只包含该等级的语法点及其直接关联。
    """
    ensure_output_dir()

    for level in LEVELS:
        level_id = f"level:{level}"
        gp_ids = set()
        for src, tgt, data in G.edges(data=True):
            if tgt == level_id and data.get("relation") == "AT_LEVEL":
                gp_ids.add(src)

        # 收集相关节点
        related_nodes = {level_id}
        related_nodes.update(gp_ids)
        for gp_id in gp_ids:
            for _, tgt, data in G.out_edges(gp_id, data=True):
                rel = data.get("relation", "")
                if rel in ("IN_SUPER_CATEGORY", "IN_SUB_CATEGORY", "HAS_TRIGGER", "HAS_KEYWORD"):
                    related_nodes.add(tgt)
                # 只包含少量例句
                if rel == "HAS_EXAMPLE":
                    related_nodes.add(tgt)

        # 构建子图数据
        nodes = []
        for nid in related_nodes:
            if nid in G:
                node = {"id": nid}
                node.update(G.nodes[nid])
                nodes.append(node)

        edges = []
        for src, tgt, data in G.edges(data=True):
            if src in related_nodes and tgt in related_nodes:
                edge = {"source": src, "target": tgt}
                edge.update(data)
                edges.append(edge)

        slice_data = {
            "level": level,
            "grammar_point_count": len(gp_ids),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

        filepath = os.path.join(OUTPUT_DIR, f"egp_kg_{level.lower()}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(slice_data, f, ensure_ascii=False, indent=2)
        print(f"  {level} 子图: {filepath} ({len(gp_ids)} 语法点, {len(nodes)} 节点)")


def export_csv(G: nx.DiGraph):
    """导出节点表 + 关系表 CSV"""
    ensure_output_dir()

    # 节点表
    node_rows = []
    for nid, data in G.nodes(data=True):
        row = {"id": nid}
        row.update({k: v for k, v in data.items()
                    if isinstance(v, (str, int, float, bool))})
        node_rows.append(row)

    nodes_df = pd.DataFrame(node_rows)
    nodes_path = os.path.join(OUTPUT_DIR, "nodes.csv")
    nodes_df.to_csv(nodes_path, index=False, encoding="utf-8-sig")
    print(f"  节点 CSV: {nodes_path} ({len(nodes_df)} 行)")

    # 关系表
    edge_rows = []
    for src, tgt, data in G.edges(data=True):
        row = {"source": src, "target": tgt}
        row.update({k: v for k, v in data.items()
                    if isinstance(v, (str, int, float, bool))})
        edge_rows.append(row)

    edges_df = pd.DataFrame(edge_rows)
    edges_path = os.path.join(OUTPUT_DIR, "edges.csv")
    edges_df.to_csv(edges_path, index=False, encoding="utf-8-sig")
    print(f"  关系 CSV: {edges_path} ({len(edges_df)} 行)")

    return nodes_path, edges_path


def export_neo4j_cypher(G: nx.DiGraph, filename: str = "import_neo4j.cypher"):
    """生成 Neo4j Cypher 导入脚本"""
    ensure_output_dir()
    filepath = os.path.join(OUTPUT_DIR, filename)

    lines = [
        "// EGP English Grammar Knowledge Graph — Neo4j Import",
        "// Auto-generated",
        "",
        "// ---- Create Constraints ----",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:GrammarPoint) REQUIRE n.id IS UNIQUE;",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Level) REQUIRE n.id IS UNIQUE;",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:SuperCategory) REQUIRE n.id IS UNIQUE;",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:SubCategory) REQUIRE n.id IS UNIQUE;",
        "",
        "// ---- Create Nodes ----",
    ]

    for nid, data in G.nodes(data=True):
        node_type = data.get("type", "Entity")
        name = data.get("name", nid).replace('"', '\\"').replace("\n", " ")
        name_zh = data.get("name_zh", "").replace('"', '\\"').replace("\n", " ")
        level = data.get("level", "")

        # 只为核心节点类型生成 Cypher
        if node_type in ("GrammarPoint", "Level", "SuperCategory", "SubCategory",
                         "TriggerLemma", "Keyword"):
            props = f'id: "{nid}", name: "{name}", name_zh: "{name_zh}"'
            if level:
                props += f', level: "{level}"'
            lines.append(f"MERGE (:{node_type} {{{props}}});")

    lines.extend(["", "// ---- Create Relationships ----"])

    core_relations = {"LEVEL_ORDER", "CATEGORY_CONTAINS", "AT_LEVEL",
                      "IN_SUPER_CATEGORY", "IN_SUB_CATEGORY",
                      "PREREQUISITE", "RELATED_BY_KEYWORD",
                      "HAS_TRIGGER", "HAS_KEYWORD"}

    for src, tgt, data in G.edges(data=True):
        rel = data.get("relation", "RELATED_TO")
        if rel not in core_relations:
            continue
        lines.append(
            f'MATCH (a {{id: "{src}"}}), (b {{id: "{tgt}"}}) '
            f'MERGE (a)-[:{rel}]->(b);'
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Neo4j Cypher: {filepath}")
    return filepath


def export_learning_path_json(G: nx.DiGraph, filename: str = "learning_path.json"):
    """
    导出结构化学习路径 JSON。
    按 Level → SuperCategory → SubCategory 三层组织，
    每个语法点标注前置依赖。
    """
    ensure_output_dir()

    path_data = {"levels": []}

    for level in LEVELS:
        level_id = f"level:{level}"
        level_entry = {
            "level": level,
            "level_info": G.nodes[level_id] if level_id in G else {},
            "categories": [],
        }

        # 该等级所有语法点
        gps = []
        for src, tgt, data in G.edges(data=True):
            if tgt == level_id and data.get("relation") == "AT_LEVEL":
                gps.append(G.nodes[src] | {"node_id": src})

        # 按大类 → 子类分组
        by_cat = defaultdict(lambda: defaultdict(list))
        for gp in gps:
            by_cat[gp.get("super_category", "")][gp.get("sub_category", "")].append(gp)

        for super_cat, subs in sorted(by_cat.items()):
            cat_entry = {
                "super_category": super_cat,
                "sub_categories": [],
            }
            for sub_cat, points in sorted(subs.items()):
                sub_entry = {
                    "sub_category": sub_cat,
                    "grammar_points": [],
                }
                for gp in points:
                    # 查找前置依赖
                    prereqs = [
                        G.nodes[s].get("egp_id", "")
                        for s, _, d in G.in_edges(gp["node_id"], data=True)
                        if d.get("relation") == "PREREQUISITE"
                    ]
                    sub_entry["grammar_points"].append({
                        "egp_id": gp.get("egp_id", ""),
                        "name_zh": gp.get("name_zh", ""),
                        "guideword": gp.get("guideword", ""),
                        "can_do": gp.get("can_do", ""),
                        "prerequisites": prereqs,
                    })
                cat_entry["sub_categories"].append(sub_entry)
            level_entry["categories"].append(cat_entry)

        path_data["levels"].append(level_entry)

    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(path_data, f, ensure_ascii=False, indent=2)
    print(f"  学习路径: {filepath}")
    return filepath


def run_all_exports(G: nx.DiGraph):
    """运行所有导出"""
    print("=" * 60)
    print("  EGP 语法知识图谱 — 数据导出")
    print("=" * 60)
    print()
    export_json(G)
    export_level_slices(G)
    export_csv(G)
    export_neo4j_cypher(G)
    export_learning_path_json(G)
    print(f"\n  所有数据已导出到 {OUTPUT_DIR}/")


if __name__ == "__main__":
    from step3_build_graph import build_knowledge_graph
    print("  构建图谱中...\n")
    G = build_knowledge_graph()
    print()
    run_all_exports(G)
