"""
Step 6: 可视化知识图谱

针对 1222 个语法点的大规模图谱，提供多种可视化视角：
  1. 核心骨架图 — 只包含 Level + SuperCategory + SubCategory
  2. 等级子图   — 某个 CEFR 等级的语法点 + 分类
  3. 前置依赖图 — 只展示 PREREQUISITE 关系
"""

import os
from collections import defaultdict

import networkx as nx
from pyvis.network import Network

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# 按实体类型配色
NODE_COLORS = {
    "Level":          "#E74C3C",
    "SuperCategory":  "#E67E22",
    "SubCategory":    "#F1C40F",
    "GrammarPoint":   "#3498DB",
    "Example":        "#95A5A6",
    "TriggerLemma":   "#9B59B6",
    "Keyword":        "#1ABC9C",
}

NODE_SIZES = {
    "Level":          50,
    "SuperCategory":  40,
    "SubCategory":    25,
    "GrammarPoint":   18,
    "Example":        10,
    "TriggerLemma":   12,
    "Keyword":        12,
}

# 按等级配色（用于语法点节点）
LEVEL_COLORS = {
    "A1": "#27AE60",
    "A2": "#2ECC71",
    "B1": "#F39C12",
    "B2": "#E67E22",
    "C1": "#E74C3C",
    "C2": "#C0392B",
}

EDGE_COLORS = {
    "LEVEL_ORDER":          "#E74C3C",
    "CATEGORY_CONTAINS":    "#E67E22",
    "AT_LEVEL":             "#95A5A6",
    "IN_SUPER_CATEGORY":    "#E67E22",
    "IN_SUB_CATEGORY":      "#F1C40F",
    "HAS_EXAMPLE":          "#95A5A6",
    "HAS_TRIGGER":          "#9B59B6",
    "HAS_KEYWORD":          "#1ABC9C",
    "PREREQUISITE":         "#E74C3C",
    "RELATED_BY_KEYWORD":   "#3498DB",
}


DEFAULT_OPTIONS = """
{
  "physics": {
    "forceAtlas2Based": {
      "gravitationalConstant": -120,
      "centralGravity": 0.012,
      "springLength": 180,
      "springConstant": 0.025,
      "damping": 0.4
    },
    "solver": "forceAtlas2Based",
    "stabilization": { "iterations": 300 }
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 100,
    "navigationButtons": true,
    "keyboard": true
  },
  "edges": {
    "smooth": { "type": "continuous" }
  }
}
"""

LARGE_GRAPH_OPTIONS = """
{
  "physics": {
    "forceAtlas2Based": {
      "gravitationalConstant": -80,
      "centralGravity": 0.008,
      "springLength": 120,
      "springConstant": 0.015,
      "damping": 0.5
    },
    "solver": "forceAtlas2Based",
    "stabilization": { "iterations": 500 }
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 100,
    "navigationButtons": true,
    "keyboard": true
  },
  "edges": {
    "smooth": { "type": "continuous" }
  }
}
"""


def _create_network(height="900px", bgcolor="#1a1a2e", options=None):
    """创建 PyVis 网络实例"""
    net = Network(
        height=height,
        width="100%",
        bgcolor=bgcolor,
        font_color="white",
        directed=True,
        notebook=False,
    )
    net.set_options(options or DEFAULT_OPTIONS)
    return net


def _inject_legend(filepath: str, items: list):
    """在 HTML 中注入图例"""
    legend_items = "".join(
        f'<div style="margin-bottom:4px;"><span style="color:{color};">●</span> {label}</div>'
        for label, color in items
    )
    legend_html = f"""
    <div id="kg-legend" style="
        position: fixed; top: 10px; right: 10px;
        background: rgba(0,0,0,0.85); color: #fff;
        padding: 15px 20px; border-radius: 10px;
        font-family: 'Segoe UI', sans-serif; font-size: 13px;
        z-index: 9999; min-width: 180px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    ">
        <div style="font-size:15px; font-weight:bold; margin-bottom:10px;
             border-bottom:1px solid #444; padding-bottom:8px;">
            EGP Grammar KG
        </div>
        {legend_items}
        <div style="margin-top:8px; font-size:11px; color:#888;">
            拖拽节点 | 滚轮缩放 | 悬浮查看详情
        </div>
    </div>
    """
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</body>", legend_html + "\n</body>")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)


def visualize_skeleton(G: nx.DiGraph, filename: str = "skeleton.html"):
    """
    可视化 1: 核心骨架图
    Level + SuperCategory + SubCategory + 它们之间的关系
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    net = _create_network()

    core_types = {"Level", "SuperCategory", "SubCategory"}
    core_rels = {"LEVEL_ORDER", "CATEGORY_CONTAINS"}

    # 统计每个子类下的语法点数量
    sub_gp_count = defaultdict(int)
    for _, _, d in G.edges(data=True):
        if d.get("relation") == "IN_SUB_CATEGORY":
            sub_gp_count[_] = sub_gp_count.get(_, 0)

    # 重新统计
    sub_gp_count = defaultdict(int)
    for src, tgt, d in G.edges(data=True):
        if d.get("relation") == "IN_SUB_CATEGORY":
            sub_gp_count[tgt] += 1

    for nid, data in G.nodes(data=True):
        ntype = data.get("type", "")
        if ntype not in core_types:
            continue
        name = data.get("name", nid)
        size = NODE_SIZES.get(ntype, 15)
        if ntype == "SubCategory":
            cnt = sub_gp_count.get(nid, 0)
            name = f"{name} ({cnt})"
            size = max(15, min(40, 10 + cnt))

        net.add_node(
            nid,
            label=name,
            title=f"{ntype}: {name}",
            color=NODE_COLORS.get(ntype, "#888"),
            size=size,
            shape="diamond" if ntype == "Level" else "dot",
            font={"size": 14 if ntype == "Level" else 11},
        )

    for src, tgt, data in G.edges(data=True):
        rel = data.get("relation", "")
        if rel not in core_rels:
            continue
        if src not in G or tgt not in G:
            continue
        src_type = G.nodes[src].get("type", "")
        tgt_type = G.nodes[tgt].get("type", "")
        if src_type not in core_types or tgt_type not in core_types:
            continue

        net.add_edge(src, tgt, color=EDGE_COLORS.get(rel, "#666"), width=2)

    filepath = os.path.join(OUTPUT_DIR, filename)
    net.save_graph(filepath)
    _inject_legend(filepath, [
        ("Level (CEFR 等级)", "#E74C3C"),
        ("SuperCategory (语法大类)", "#E67E22"),
        ("SubCategory (语法子类)", "#F1C40F"),
    ])
    print(f"  骨架图: {filepath}")
    return filepath


def visualize_level(G: nx.DiGraph, level: str, filename: str = None):
    """
    可视化 2: 等级子图
    某个 CEFR 等级的所有语法点，按大类着色
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if filename is None:
        filename = f"level_{level.lower()}.html"

    net = _create_network()

    level_id = f"level:{level}"
    gp_ids = set()
    for src, tgt, d in G.edges(data=True):
        if tgt == level_id and d.get("relation") == "AT_LEVEL":
            gp_ids.add(src)

    # 收集关联的 SuperCategory 和 SubCategory
    related_subs = set()
    related_supers = set()
    for gp_id in gp_ids:
        for _, tgt, d in G.out_edges(gp_id, data=True):
            if d.get("relation") == "IN_SUB_CATEGORY":
                related_subs.add(tgt)
            elif d.get("relation") == "IN_SUPER_CATEGORY":
                related_supers.add(tgt)

    # 为大类分配颜色
    super_list = sorted(related_supers)
    palette = [
        "#E74C3C", "#3498DB", "#2ECC71", "#E67E22", "#9B59B6",
        "#1ABC9C", "#F39C12", "#E91E63", "#00BCD4", "#FF5722",
        "#795548", "#607D8B", "#4CAF50", "#FF9800", "#673AB7",
        "#009688", "#CDDC39", "#FFC107", "#03A9F4",
    ]
    super_color = {s: palette[i % len(palette)] for i, s in enumerate(super_list)}

    # 添加 Level 节点
    net.add_node(level_id, label=level, color="#E74C3C", size=60,
                 shape="diamond", font={"size": 20})

    # 添加 SuperCategory 节点
    for sc_id in related_supers:
        name = G.nodes[sc_id].get("name", sc_id)
        net.add_node(sc_id, label=name, color=super_color.get(sc_id, "#E67E22"),
                     size=35, shape="dot", font={"size": 13})

    # 添加 SubCategory 节点
    for sub_id in related_subs:
        name = G.nodes[sub_id].get("name", sub_id)
        sc = G.nodes[sub_id].get("super_category", "")
        sc_id = f"super:{sc}"
        net.add_node(sub_id, label=name, color=super_color.get(sc_id, "#F1C40F"),
                     size=22, shape="dot", font={"size": 10},
                     borderWidth=2, borderWidthSelected=3)

    # 添加 GrammarPoint 节点
    for gp_id in gp_ids:
        gp = G.nodes[gp_id]
        name_zh = gp.get("name_zh", "")
        label = name_zh[:15] + "..." if len(name_zh) > 15 else name_zh
        sc = gp.get("super_category", "")
        sc_id = f"super:{sc}"

        title = (f"<b>{gp.get('egp_id', '')}</b><br>"
                 f"{name_zh}<br>"
                 f"<i>{gp.get('guideword', '')}</i><br>"
                 f"{gp.get('can_do', '')[:100]}")

        net.add_node(gp_id, label=label, title=title,
                     color=super_color.get(sc_id, "#3498DB"),
                     size=14, font={"size": 9})

    # 添加边
    for gp_id in gp_ids:
        for _, tgt, d in G.out_edges(gp_id, data=True):
            rel = d.get("relation", "")
            if rel == "IN_SUB_CATEGORY" and tgt in related_subs:
                net.add_edge(gp_id, tgt, color="#44444466", width=1)
            elif rel == "PREREQUISITE" and tgt in gp_ids:
                net.add_edge(gp_id, tgt, color="#E74C3C", width=3, dashes=False)

    for sc_id in related_supers:
        for _, tgt, d in G.out_edges(sc_id, data=True):
            if d.get("relation") == "CATEGORY_CONTAINS" and tgt in related_subs:
                net.add_edge(sc_id, tgt, color="#E67E2288", width=2)

    filepath = os.path.join(OUTPUT_DIR, filename)
    net.save_graph(filepath)

    legend_items = [(G.nodes[s].get("name", ""), super_color.get(s, "#888"))
                    for s in super_list]
    _inject_legend(filepath, legend_items)
    print(f"  {level} 等级图: {filepath} ({len(gp_ids)} 语法点)")
    return filepath


def visualize_prerequisites(G: nx.DiGraph, filename: str = "prerequisites.html"):
    """
    可视化 3: 前置依赖图
    只展示 GrammarPoint 之间的 PREREQUISITE 关系
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    net = _create_network()

    prereq_nodes = set()
    prereq_edges = []
    for src, tgt, d in G.edges(data=True):
        if d.get("relation") == "PREREQUISITE":
            prereq_nodes.add(src)
            prereq_nodes.add(tgt)
            prereq_edges.append((src, tgt))

    for nid in prereq_nodes:
        nd = G.nodes[nid]
        level = nd.get("level", "")
        name_zh = nd.get("name_zh", "")
        label = f"[{level}] {name_zh[:12]}"

        net.add_node(
            nid,
            label=label,
            title=f"{nd.get('egp_id', '')}: {name_zh}",
            color=LEVEL_COLORS.get(level, "#3498DB"),
            size=20,
            font={"size": 10},
        )

    for src, tgt in prereq_edges:
        net.add_edge(src, tgt, color="#E74C3C88", width=2,
                     arrows={"to": {"enabled": True, "scaleFactor": 0.8}})

    filepath = os.path.join(OUTPUT_DIR, filename)
    net.save_graph(filepath)
    _inject_legend(filepath, _level_legend_items())
    print(f"  依赖图: {filepath} ({len(prereq_nodes)} 节点, {len(prereq_edges)} 条依赖)")
    return filepath


def visualize_full_a1_c2(G: nx.DiGraph, filename: str = "full_a1_c2.html"):
    """
    可视化 4: 完整 A1-C2 图谱
    所有 1222 个语法点，按等级着色，显示分类结构和前置依赖
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    net = _create_network(height="1000px", options=LARGE_GRAPH_OPTIONS)

    # 添加 SuperCategory 节点作为锚点
    super_ids = set()
    for nid, data in G.nodes(data=True):
        if data.get("type") == "SuperCategory":
            super_ids.add(nid)
            net.add_node(nid, label=data.get("name", nid),
                         color="#FFFFFF", size=45, shape="diamond",
                         font={"size": 16, "color": "white", "bold": True},
                         borderWidth=3)

    # 添加 SubCategory 节点
    sub_ids = set()
    for nid, data in G.nodes(data=True):
        if data.get("type") == "SubCategory":
            sub_ids.add(nid)
            sc = data.get("super_category", "")
            net.add_node(nid, label=data.get("name", nid),
                         color="#FFFFFF44", size=18, shape="dot",
                         font={"size": 9, "color": "#AAAAAA"})

    # SuperCategory → SubCategory 边
    for src, tgt, d in G.edges(data=True):
        if d.get("relation") == "CATEGORY_CONTAINS" and src in super_ids and tgt in sub_ids:
            net.add_edge(src, tgt, color="#FFFFFF22", width=1)

    # 添加所有 GrammarPoint 节点，按等级着色
    gp_ids = set()
    for nid, data in G.nodes(data=True):
        if data.get("type") != "GrammarPoint":
            continue
        gp_ids.add(nid)
        level = data.get("level", "")
        name_zh = data.get("name_zh", "")
        label = name_zh[:10] + ".." if len(name_zh) > 10 else name_zh

        title = (f"<b>{data.get('egp_id', '')}</b> [{level}]<br>"
                 f"{name_zh}<br>"
                 f"<i>{data.get('guideword', '')}</i><br>"
                 f"Category: {data.get('super_category', '')} &gt; {data.get('sub_category', '')}<br>"
                 f"{data.get('can_do', '')[:120]}")

        net.add_node(nid, label=label, title=title,
                     color=LEVEL_COLORS.get(level, "#3498DB"),
                     size=10, font={"size": 7})

    # GrammarPoint → SubCategory 边（轻量级）
    for src, tgt, d in G.edges(data=True):
        if d.get("relation") == "IN_SUB_CATEGORY" and src in gp_ids and tgt in sub_ids:
            net.add_edge(src, tgt, color="#44444422", width=0.5)

    # PREREQUISITE 边（高亮）
    for src, tgt, d in G.edges(data=True):
        if d.get("relation") == "PREREQUISITE" and src in gp_ids and tgt in gp_ids:
            net.add_edge(src, tgt, color="#E74C3CBB", width=2,
                         arrows={"to": {"enabled": True, "scaleFactor": 0.6}})

    filepath = os.path.join(OUTPUT_DIR, filename)
    net.save_graph(filepath)
    _inject_legend(filepath, _level_legend_items() + [
        ("─── PREREQUISITE 依赖", "#E74C3C"),
        ("◆ SuperCategory 语法大类", "#FFFFFF"),
    ])
    print(f"  完整 A1-C2 图谱: {filepath} ({len(gp_ids)} 语法点)")
    return filepath


def visualize_topic(G: nx.DiGraph, topic_name: str,
                    super_categories: list, filename: str = None):
    """
    可视化 5: 主题子图
    按指定的 SuperCategory 过滤，展示该主题下的完整学习路径
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if filename is None:
        filename = f"topic_{topic_name.lower().replace(' ', '_')}.html"

    net = _create_network()

    # 收集目标语法点
    gp_ids = set()
    for nid, data in G.nodes(data=True):
        if data.get("type") == "GrammarPoint" and data.get("super_category") in super_categories:
            gp_ids.add(nid)

    # 收集关联子类
    related_subs = set()
    for gp_id in gp_ids:
        for _, tgt, d in G.out_edges(gp_id, data=True):
            if d.get("relation") == "IN_SUB_CATEGORY":
                related_subs.add(tgt)

    # 添加子类节点
    for sub_id in related_subs:
        name = G.nodes[sub_id].get("name", sub_id)
        net.add_node(sub_id, label=name, color="#FFFFFF88", size=28,
                     shape="dot", font={"size": 12, "color": "#DDD"})

    # 添加语法点节点
    for gp_id in gp_ids:
        gp = G.nodes[gp_id]
        level = gp.get("level", "")
        name_zh = gp.get("name_zh", "")
        label = f"[{level}] {name_zh[:12]}"

        title = (f"<b>{gp.get('egp_id', '')}</b> [{level}]<br>"
                 f"{name_zh}<br>"
                 f"<i>{gp.get('guideword', '')}</i><br>"
                 f"{gp.get('sub_category', '')}")

        net.add_node(gp_id, label=label, title=title,
                     color=LEVEL_COLORS.get(level, "#3498DB"),
                     size=16, font={"size": 9})

    # 边
    for gp_id in gp_ids:
        for _, tgt, d in G.out_edges(gp_id, data=True):
            if d.get("relation") == "IN_SUB_CATEGORY" and tgt in related_subs:
                net.add_edge(gp_id, tgt, color="#44444444", width=1)
            elif d.get("relation") == "PREREQUISITE" and tgt in gp_ids:
                net.add_edge(gp_id, tgt, color="#E74C3CBB", width=3,
                             arrows={"to": {"enabled": True, "scaleFactor": 0.8}})

    filepath = os.path.join(OUTPUT_DIR, filename)
    net.save_graph(filepath)
    _inject_legend(filepath, _level_legend_items() + [
        ("─── PREREQUISITE 依赖", "#E74C3C"),
    ])
    cat_str = "+".join(super_categories)
    print(f"  主题图 [{cat_str}]: {filepath} ({len(gp_ids)} 语法点)")
    return filepath


def visualize_shortest_path(G: nx.DiGraph, path_nodes: list,
                            target_ids: list = None,
                            title: str = "最短学习路径",
                            filename: str = "shortest_path.html"):
    """
    可视化 6: 最短学习路径
    高亮学习路径上的节点和 PREREQUISITE 边，
    用序号标注学习顺序，目标节点特殊标记。

    Args:
        G: 知识图谱
        path_nodes: 路径节点 ID 列表（已排序）
        target_ids: 最终目标节点 ID 列表（gp:GG-xx-xxx 格式）
        title: 图标题
        filename: 输出文件名
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    net = _create_network()

    if target_ids is None:
        target_ids = []
    target_set = set(target_ids)
    path_set = set(path_nodes)

    # 收集路径节点涉及的子类
    related_subs = set()
    for nid in path_nodes:
        for _, tgt, d in G.out_edges(nid, data=True):
            if d.get("relation") == "IN_SUB_CATEGORY":
                related_subs.add(tgt)

    # 添加 SubCategory 节点（淡化背景）
    for sub_id in related_subs:
        name = G.nodes[sub_id].get("name", sub_id)
        net.add_node(sub_id, label=name, color="#FFFFFF33", size=30,
                     shape="dot", font={"size": 12, "color": "#888"})

    # 添加路径上的语法点节点
    for i, nid in enumerate(path_nodes):
        nd = G.nodes[nid]
        level = nd.get("level", "")
        name_zh = nd.get("name_zh", "")
        egp_id = nd.get("egp_id", "")
        is_target = nid in target_set

        label = f"#{i+1} {name_zh[:15]}"
        border_color = "#FFD700" if is_target else LEVEL_COLORS.get(level, "#3498DB")
        node_color = LEVEL_COLORS.get(level, "#3498DB")

        title_html = (
            f"<b>#{i+1} {egp_id}</b> [{level}]<br>"
            f"{name_zh}<br>"
            f"<i>{nd.get('guideword', '')}</i><br>"
            f"Category: {nd.get('super_category', '')} &gt; {nd.get('sub_category', '')}<br>"
            f"{nd.get('can_do', '')[:150]}<br>"
        )
        if is_target:
            title_html += "<br><b style='color:#FFD700;'>★ 目标语法点</b>"

        # 检查来源
        has_llm_prereq = False
        for s, _, d in G.in_edges(nid, data=True):
            if d.get("relation") == "PREREQUISITE" and d.get("source") == "llm_annotation" and s in path_set:
                has_llm_prereq = True
                break

        if has_llm_prereq:
            title_html += "<br><span style='color:#9B59B6;'>跨类依赖 (LLM 标注)</span>"

        net.add_node(
            nid, label=label, title=title_html,
            color={"background": node_color, "border": border_color},
            size=30 if is_target else 22,
            shape="star" if is_target else "dot",
            font={"size": 12, "color": "white", "bold": is_target},
            borderWidth=4 if is_target else 2,
        )

    # 添加 PREREQUISITE 边（路径内的）
    for nid in path_nodes:
        for src, _, d in G.in_edges(nid, data=True):
            if d.get("relation") == "PREREQUISITE" and src in path_set:
                is_llm = d.get("source") == "llm_annotation"
                color = "#9B59B6" if is_llm else "#E74C3C"
                label = "跨类" if is_llm else ""
                net.add_edge(
                    src, nid, color=color, width=4,
                    arrows={"to": {"enabled": True, "scaleFactor": 1.0}},
                    label=label,
                    font={"size": 9, "color": color},
                )

    # 语法点 → SubCategory 连线（淡化）
    for nid in path_nodes:
        for _, tgt, d in G.out_edges(nid, data=True):
            if d.get("relation") == "IN_SUB_CATEGORY" and tgt in related_subs:
                net.add_edge(nid, tgt, color="#44444433", width=1, dashes=True)

    filepath = os.path.join(OUTPUT_DIR, filename)
    net.save_graph(filepath)

    # 注入增强图例 + 标题
    legend_items = _level_legend_items() + [
        ("─── 同类 PREREQUISITE", "#E74C3C"),
        ("─── 跨类 PREREQUISITE (LLM)", "#9B59B6"),
        ("★ 目标语法点", "#FFD700"),
    ]
    _inject_legend(filepath, legend_items)
    _inject_path_title(filepath, title, len(path_nodes), target_ids, G)

    print(f"  路径图: {filepath} ({len(path_nodes)} 步)")
    return filepath


def _inject_path_title(filepath, title, step_count, target_ids, G):
    """在 HTML 中注入路径标题和步骤列表"""
    targets_str = ", ".join(
        G.nodes[tid].get("egp_id", tid.replace("gp:", ""))
        for tid in target_ids if tid in G
    )

    title_html = f"""
    <div id="path-title" style="
        position: fixed; top: 10px; left: 10px;
        background: rgba(0,0,0,0.9); color: #fff;
        padding: 15px 25px; border-radius: 10px;
        font-family: 'Segoe UI', sans-serif; font-size: 14px;
        z-index: 9999; max-width: 380px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    ">
        <div style="font-size:18px; font-weight:bold; margin-bottom:8px; color:#FFD700;">
            {title}
        </div>
        <div style="color:#CCC; margin-bottom:5px;">
            目标: {targets_str}
        </div>
        <div style="color:#AAA; font-size:12px;">
            共 {step_count} 个语法点 | 点击节点查看详情
        </div>
    </div>
    """
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</body>", title_html + "\n</body>")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)


def _level_legend_items():
    """等级图例"""
    return [
        (f"{lvl} ({info})", color)
        for lvl, color in LEVEL_COLORS.items()
        for info in [{"A1": "入门", "A2": "基础", "B1": "中级",
                      "B2": "中高级", "C1": "高级", "C2": "精通"}[lvl]]
    ]


def run_visualizations(G: nx.DiGraph):
    """运行所有可视化"""
    from step1_ontology import LEVELS as ALL_LEVELS

    print("=" * 60)
    print("  EGP 语法知识图谱 — 可视化")
    print("=" * 60)
    print()

    # 1. 骨架图
    visualize_skeleton(G)

    # 2. 所有 6 个等级子图
    for lvl in ALL_LEVELS:
        visualize_level(G, lvl)

    # 3. 完整 A1-C2 图谱
    visualize_full_a1_c2(G)

    # 4. 前置依赖图
    visualize_prerequisites(G)

    # 5. 主题图
    visualize_topic(G, "tenses", ["PAST", "PRESENT", "FUTURE"],
                    filename="topic_tenses.html")
    visualize_topic(G, "clauses", ["CLAUSES"],
                    filename="topic_clauses.html")
    visualize_topic(G, "modality", ["MODALITY"],
                    filename="topic_modality.html")
    visualize_topic(G, "sentence_structure",
                    ["CLAUSES", "CONJUNCTIONS", "PASSIVES", "NEGATION",
                     "QUESTIONS", "REPORTED SPEECH"],
                    filename="topic_sentence_structure.html")

    print(f"\n  用浏览器打开 output/*.html 即可交互查看")


if __name__ == "__main__":
    from step3_build_graph import build_knowledge_graph
    print("  构建图谱中...\n")
    G = build_knowledge_graph()
    print()
    run_visualizations(G)
