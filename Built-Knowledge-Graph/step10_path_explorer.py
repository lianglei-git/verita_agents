"""
Step 10: 交互式学习序列探索器

启动一个 Web 服务，让用户可以：
  1. 搜索/浏览所有语法点
  2. 选择一个或多个目标语法点
  3. 实时计算目标语法点的前置依赖闭包，生成学习序列
  4. 查看每个节点的详细信息和依赖关系

定位说明：
  这里计算的"学习序列"是"前置依赖闭包 + 拓扑排序"的结果，
  不是图论意义上的最短路径。所有前置依赖均来自类内规则推导。

运行:
  python step10_path_explorer.py              # 启动服务 (默认端口 5002)
  python step10_path_explorer.py --port 8080  # 指定端口
"""

import json
import os
import argparse

from flask import Flask, jsonify, request, Response

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

import networkx as nx

from step1_ontology import LEVELS
from step3_build_graph import build_knowledge_graph
from step9_merge_annotations import (
    load_cross_prerequisites,
    merge_cross_prerequisites,
    find_prerequisites_for,
    find_prerequisite_closure,
)

app = Flask(__name__)

G = None
gp_index = {}


def init_graph():
    """初始化知识图谱（类内规则推导的保守版图谱）"""
    global G, gp_index

    print("  构建知识图谱...")
    G = build_knowledge_graph()

    # 可选：若存在 LLM 跨类标注文件则叠加（探索性，默认不强依赖）
    annotations = load_cross_prerequisites()
    if annotations:
        added = merge_cross_prerequisites(G, annotations)
        print(f"  [可选] 叠加跨类依赖: +{added} 条")

    for nid, data in G.nodes(data=True):
        if data.get("type") == "GrammarPoint":
            egp_id = data.get("egp_id", "")
            gp_index[egp_id] = {
                "node_id": nid,
                "egp_id": egp_id,
                "name_zh": data.get("name_zh", ""),
                "level": data.get("level", ""),
                "super_category": data.get("super_category", ""),
                "sub_category": data.get("sub_category", ""),
                "guideword": data.get("guideword", ""),
                "can_do": data.get("can_do", ""),
            }

    print(f"  语法点索引: {len(gp_index)} 条")


# ============================================================
# API
# ============================================================

@app.route("/")
def index():
    return Response(HTML_PAGE, content_type="text/html; charset=utf-8")


@app.route("/api/grammar_points")
def api_grammar_points():
    q = request.args.get("q", "").strip().lower()
    level = request.args.get("level", "").strip()
    cat = request.args.get("category", "").strip()

    results = []
    for info in gp_index.values():
        if level and info["level"] != level:
            continue
        if cat and info["super_category"] != cat:
            continue
        if q:
            searchable = f"{info['egp_id']} {info['name_zh']} {info['guideword']} {info['sub_category']}".lower()
            if q not in searchable:
                continue
        results.append(info)

    results.sort(key=lambda x: (
        LEVELS.index(x["level"]) if x["level"] in LEVELS else 99,
        x["super_category"], x["egp_id"]
    ))
    return jsonify({"items": results, "total": len(results)})


@app.route("/api/categories")
def api_categories():
    supers = sorted(set(v["super_category"] for v in gp_index.values()))
    return jsonify({"levels": LEVELS, "super_categories": supers})


@app.route("/api/detail/<egp_id>")
def api_detail(egp_id):
    info = gp_index.get(egp_id)
    if not info:
        return jsonify({"error": "not found"}), 404

    nid = info["node_id"]

    prereqs = []
    for src, _, d in G.in_edges(nid, data=True):
        if d.get("relation") == "PREREQUISITE":
            src_data = G.nodes[src]
            prereqs.append({
                "egp_id": src_data.get("egp_id", ""),
                "name_zh": src_data.get("name_zh", ""),
                "level": src_data.get("level", ""),
                "sub_category": src_data.get("sub_category", ""),
                "source": d.get("source", "inferred"),
            })

    successors = []
    for _, tgt, d in G.out_edges(nid, data=True):
        if d.get("relation") == "PREREQUISITE":
            tgt_data = G.nodes[tgt]
            successors.append({
                "egp_id": tgt_data.get("egp_id", ""),
                "name_zh": tgt_data.get("name_zh", ""),
                "level": tgt_data.get("level", ""),
                "sub_category": tgt_data.get("sub_category", ""),
            })

    result = dict(info)
    result["prerequisites"] = prereqs
    result["successors"] = successors
    return jsonify(result)


@app.route("/api/preset_paths")
def api_preset_paths():
    """返回所有可用的预设学习路径列表"""
    index_path = os.path.join(OUTPUT_DIR, "paths", "index.json")
    if not os.path.exists(index_path):
        return jsonify({"error": "index.json 未找到，请先运行 step7"}), 404
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    return jsonify(index)


@app.route("/api/preset_path/<path_id>")
def api_preset_path(path_id):
    """
    加载指定预设路径，返回与 /api/shortest_path 兼容的 nodes/edges 格式。
    """
    # 先找 output/paths/<path_id>.json，再兼容 output/path_<path_id>.json
    candidates = [
        os.path.join(OUTPUT_DIR, "paths", f"{path_id}.json"),
        os.path.join(OUTPUT_DIR, f"path_{path_id}.json"),
    ]
    filepath = next((p for p in candidates if os.path.exists(p)), None)
    if not filepath:
        return jsonify({"error": f"路径 '{path_id}' 不存在"}), 404

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_items = data.get("items", [])
    stats = data.get("statistics", {})

    # 建立 egp_id → node_id 映射（只映射路径内的节点）
    path_egp_ids = {item["egp_id"] for item in raw_items}

    nodes = []
    for item in raw_items:
        prereqs_in_path = [
            {"egp_id": pid, "source": "inferred"}
            for pid in item.get("prerequisites", [])
            if pid in path_egp_ids
        ]
        nid = f"gp:{item['egp_id']}"
        nodes.append({
            "id": nid,
            "egp_id": item["egp_id"],
            "name_zh": item.get("name_zh", ""),
            "level": item.get("level", ""),
            "super_category": item.get("super_category", ""),
            "sub_category": item.get("sub_category", ""),
            "guideword": item.get("guideword", ""),
            "can_do": item.get("can_do", ""),
            "order": item.get("order", 0),
            "is_target": False,
            "prereqs_in_path": prereqs_in_path,
        })

    edges = []
    for item in raw_items:
        nid = f"gp:{item['egp_id']}"
        for pid in item.get("prerequisites", []):
            if pid in path_egp_ids:
                edges.append({
                    "from": f"gp:{pid}",
                    "to": nid,
                    "source": "inferred",
                })

    return jsonify({
        "path_id": path_id,
        "name": data.get("name", path_id),
        "description": data.get("description", ""),
        "total_steps": len(nodes),
        "statistics": stats,
        "nodes": nodes,
        "edges": edges,
    })


@app.route("/api/shortest_path", methods=["POST"])
def api_shortest_path():
    """
    计算目标语法点的前置依赖闭包学习序列。
    接口名保留 /api/shortest_path 以兼容前端，但语义已更正为"前置依赖闭包"。
    """
    data = request.json or {}
    target_ids = data.get("targets", [])
    include_llm = data.get("include_llm", False)

    if not target_ids:
        return jsonify({"error": "请至少选择一个目标语法点"}), 400

    valid_targets = [tid for tid in target_ids if tid in gp_index]
    if not valid_targets:
        return jsonify({"error": "无效的语法点 ID"}), 400

    path = find_prerequisite_closure(G, valid_targets, include_llm=include_llm)

    target_node_ids = {f"gp:{tid}" for tid in valid_targets}
    path_set = set(path)

    nodes = []
    for i, nid in enumerate(path):
        nd = G.nodes[nid]
        egp_id = nd.get("egp_id", "")
        is_target = nid in target_node_ids

        prereqs_in_path = []
        for src, _, d in G.in_edges(nid, data=True):
            if d.get("relation") == "PREREQUISITE" and src in path_set:
                prereqs_in_path.append({
                    "egp_id": G.nodes[src].get("egp_id", ""),
                    "source": d.get("source", "inferred"),
                })

        nodes.append({
            "id": nid,
            "egp_id": egp_id,
            "name_zh": nd.get("name_zh", ""),
            "level": nd.get("level", ""),
            "super_category": nd.get("super_category", ""),
            "sub_category": nd.get("sub_category", ""),
            "guideword": nd.get("guideword", ""),
            "can_do": nd.get("can_do", ""),
            "order": i,
            "is_target": is_target,
            "prereqs_in_path": prereqs_in_path,
        })

    edges = []
    for nid in path:
        for src, _, d in G.in_edges(nid, data=True):
            if d.get("relation") == "PREREQUISITE" and src in path_set:
                edges.append({
                    "from": src,
                    "to": nid,
                    "source": d.get("source", "inferred"),
                })

    return jsonify({
        "targets": valid_targets,
        "total_steps": len(path),
        "nodes": nodes,
        "edges": edges,
    })


# ============================================================
# 内嵌 HTML（纯 CSS 流程图，零第三方依赖）
# ============================================================

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EGP 学习序列探索器</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f1a;color:#e0e0e0;height:100vh;display:flex;overflow:hidden}

.sidebar{width:380px;min-width:380px;background:#1a1a2e;display:flex;flex-direction:column;border-right:1px solid #2a2a4a}
.sidebar-header{padding:14px 20px;background:#16213e;border-bottom:1px solid #2a2a4a}
.sidebar-header h1{font-size:17px;color:#FFD700;margin-bottom:2px}
.sidebar-header p{font-size:11px;color:#888}

/* 模式切换 Tab */
.mode-tabs{display:flex;background:#16213e;border-bottom:1px solid #2a2a4a}
.mode-tab{flex:1;padding:9px 0;text-align:center;font-size:13px;cursor:pointer;color:#777;border-bottom:2px solid transparent;transition:color .15s}
.mode-tab.act{color:#FFD700;border-bottom-color:#FFD700}
.mode-tab:hover:not(.act){color:#aaa}

/* 自由探索 - 目标区 */
.targets-section{padding:12px 16px;background:#16213e;border-bottom:1px solid #2a2a4a}
.targets-section h3{font-size:13px;color:#aaa;margin-bottom:8px}
.targets-list{display:flex;flex-wrap:wrap;gap:6px;min-height:32px}
.target-tag{display:inline-flex;align-items:center;gap:4px;background:#2a2a5a;border:1px solid #FFD700;color:#FFD700;padding:3px 10px;border-radius:14px;font-size:12px}
.target-tag .rm{cursor:pointer;opacity:.7;margin-left:2px}
.target-tag .rm:hover{opacity:1}

.btn-go{margin-top:10px;width:100%;padding:9px;background:linear-gradient(135deg,#E74C3C,#C0392B);color:#fff;border:none;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer}
.btn-go:hover{opacity:.9}
.btn-go:disabled{opacity:.4;cursor:not-allowed}

.search-section{padding:10px 16px;border-bottom:1px solid #2a2a4a}
.si{width:100%;padding:8px 12px;background:#0f0f1a;border:1px solid #333;border-radius:6px;color:#e0e0e0;font-size:13px;outline:none}
.si:focus{border-color:#3498DB}
.si::placeholder{color:#555}
.fr{display:flex;gap:6px;margin-top:8px}
.fs{flex:1;padding:6px 8px;background:#0f0f1a;border:1px solid #333;border-radius:4px;color:#e0e0e0;font-size:12px;outline:none}

.gp-list{flex:1;overflow-y:auto;padding:8px 0}
.gp-list::-webkit-scrollbar{width:6px}
.gp-list::-webkit-scrollbar-thumb{background:#333;border-radius:3px}

.gi{padding:10px 16px;cursor:pointer;border-bottom:1px solid #1f1f3a;transition:background .15s}
.gi:hover{background:#222244}
.gi.sel{background:#2a2a5a;border-left:3px solid #FFD700}
.gi .gh{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px}
.gi .gid{font-size:11px;color:#888;font-family:monospace}
.gi .glv{font-size:10px;padding:1px 6px;border-radius:3px;font-weight:600}
.gi .gn{font-size:13px;color:#ddd;line-height:1.3}
.gi .gc{font-size:11px;color:#666;margin-top:2px}
.gi .ba{display:inline-block;margin-top:4px;padding:2px 8px;background:transparent;border:1px solid #FFD700;color:#FFD700;border-radius:3px;font-size:11px;cursor:pointer}
.gi .ba:hover{background:#FFD70022}

/* 预设路径列表 */
.preset-list{flex:1;overflow-y:auto;padding:8px 0}
.preset-list::-webkit-scrollbar{width:6px}
.preset-list::-webkit-scrollbar-thumb{background:#333;border-radius:3px}
.pi-card{padding:12px 16px;cursor:pointer;border-bottom:1px solid #1f1f3a;transition:background .15s}
.pi-card:hover{background:#222244}
.pi-card.act{background:#1e2a1e;border-left:3px solid #27AE60}
.pi-card .pn{font-size:14px;color:#ddd;margin-bottom:3px}
.pi-card .pd{font-size:11px;color:#666;line-height:1.4}
.pi-card .pm{display:flex;gap:8px;margin-top:5px;flex-wrap:wrap}
.pi-card .pt{font-size:10px;background:#1a2a3a;border:1px solid #2a3a4a;color:#3498DB;padding:1px 7px;border-radius:10px}

.lA1{background:#27AE60;color:#fff}.lA2{background:#2ECC71;color:#fff}
.lB1{background:#F39C12;color:#fff}.lB2{background:#E67E22;color:#fff}
.lC1{background:#E74C3C;color:#fff}.lC2{background:#C0392B;color:#fff}

.main{flex:1;display:flex;flex-direction:column;position:relative}
#gc{flex:1;overflow:auto;padding:30px;background:#0f0f1a}
.ph{display:flex;align-items:center;justify-content:center;height:100%;color:#444;font-size:16px;flex-direction:column;gap:12px}

/* 流程图 */
.fs-bar{display:flex;gap:20px;margin-bottom:24px;padding:12px 16px;background:#16213e;border-radius:8px;font-size:13px;color:#aaa;flex-wrap:wrap}
.fs-bar .v{color:#FFD700;font-weight:600}
.fs-bar .ptitle{font-size:15px;color:#eee;font-weight:600;width:100%;margin-bottom:2px}
.fs-bar .pdesc{font-size:12px;color:#666;width:100%}

.lvg{margin-bottom:16px}
.lvl{display:inline-block;padding:4px 14px;border-radius:4px;font-size:13px;font-weight:700;color:#fff;margin-bottom:10px}

.frow{display:flex;flex-wrap:wrap;gap:12px;padding-left:16px}

.fc{position:relative;background:#1a1a2e;border:1px solid #2a2a4a;border-radius:10px;padding:12px 14px;width:270px;cursor:pointer;transition:border-color .2s,box-shadow .2s}
.fc:hover{border-color:#3498DB;box-shadow:0 0 12px rgba(52,152,219,.25)}
.fc.tgt{border-color:#FFD700;box-shadow:0 0 16px rgba(255,215,0,.2)}
.fc .co{position:absolute;top:-10px;left:-10px;width:26px;height:26px;border-radius:50%;background:#3498DB;color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center}
.fc.tgt .co{background:#FFD700;color:#000}
.fc .ci{font-size:11px;color:#888;font-family:monospace}
.fc .cn{font-size:14px;color:#eee;margin:4px 0 2px;line-height:1.35}
.fc .cc{font-size:11px;color:#666}
.fc .cp{margin-top:6px;font-size:11px;color:#E74C3C}
.fc .cp .lm{color:#9B59B6}
.fc .ts{position:absolute;top:8px;right:10px;font-size:16px;color:#FFD700}
.fc .gw{font-size:11px;color:#557;margin-top:3px;font-style:italic}

.arw{display:flex;align-items:center;padding-left:32px;margin:4px 0;color:#555}

/* 详情面板 */
.dp{position:fixed;top:60px;right:20px;width:360px;max-height:calc(100vh - 80px);background:rgba(22,33,62,.97);border:1px solid #2a2a4a;border-radius:10px;padding:18px;z-index:50;overflow-y:auto;display:none;backdrop-filter:blur(10px);box-shadow:0 8px 32px rgba(0,0,0,.5)}
.dp.act{display:block}
.dp h2{font-size:15px;color:#FFD700;margin-bottom:4px}
.dp .dx{position:absolute;top:12px;right:16px;cursor:pointer;color:#888;font-size:20px}
.dp .dx:hover{color:#fff}
.df{margin-top:8px}
.df label{font-size:11px;color:#888;display:block;margin-bottom:2px}
.df .val{font-size:13px;color:#ddd;line-height:1.4}
.dpr{margin-top:10px}
.dpr h4{font-size:12px;color:#E74C3C;margin-bottom:4px}
.dpi{font-size:12px;color:#aaa;padding:3px 0;cursor:pointer}
.dpi:hover{color:#3498DB}
.dpi .lb{font-size:9px;background:#9B59B6;color:#fff;padding:1px 4px;border-radius:3px;margin-left:4px}
</style>
</head>
<body>
<div class="sidebar">
  <div class="sidebar-header">
    <h1>EGP 学习序列探索器</h1>
    <p>浏览语法知识图谱 &middot; 查看前置依赖学习序列</p>
  </div>

  <!-- 模式切换 Tab -->
  <div class="mode-tabs">
    <div class="mode-tab act" id="tab-free" onclick="switchMode('free')">自由探索</div>
    <div class="mode-tab" id="tab-preset" onclick="switchMode('preset')">预设路径</div>
  </div>

  <!-- 自由探索面板 -->
  <div id="panel-free">
    <div class="targets-section">
      <h3>目标语法点 <span id="tc">(0)</span></h3>
      <div class="targets-list" id="tl"></div>
      <button class="btn-go" id="bg" disabled onclick="compute()">生成学习序列</button>
    </div>
    <div class="search-section">
      <input type="text" class="si" id="si" placeholder="搜索 (ID / 中文名 / 关键词)..." oninput="dsearch()">
      <div class="fr">
        <select class="fs" id="fl" onchange="loadGP()"><option value="">全部等级</option></select>
        <select class="fs" id="fcat" onchange="loadGP()"><option value="">全部分类</option></select>
      </div>
    </div>
    <div class="gp-list" id="gl"></div>
  </div>

  <!-- 预设路径面板 -->
  <div id="panel-preset" style="display:none;flex:1;display:none;flex-direction:column;overflow-y:auto;">
    <div style="padding:10px 16px;border-bottom:1px solid #2a2a4a;font-size:11px;color:#666">
      点击路径即可在右侧展示完整学习序列
    </div>
    <div class="preset-list" id="pl"></div>
  </div>
</div>

<div class="main">
  <div id="gc">
    <div class="ph" id="ph">
      <div style="font-size:48px;opacity:.3">&#128218;</div>
      <div style="color:#555">左侧选择语法点或预设路径</div>
      <div style="font-size:12px;color:#333">自由探索：选目标 → 生成前置依赖序列 &nbsp;|&nbsp; 预设路径：直接查看完整主题学习清单</div>
    </div>
  </div>
  <div class="dp" id="dp">
    <span class="dx" onclick="cdp()">&times;</span>
    <h2 id="dt"></h2>
    <div id="dc"></div>
  </div>
</div>

<script>
const LC={A1:'#27AE60',A2:'#2ECC71',B1:'#F39C12',B2:'#E67E22',C1:'#E74C3C',C2:'#C0392B'};
const LO=['A1','A2','B1','B2','C1','C2'];
let tgts=new Set(),stm=null,curMode='free',curPreset=null;

// ── 模式切换 ──────────────────────────────────────────────
function switchMode(m){
  curMode=m;
  document.getElementById('tab-free').classList.toggle('act',m==='free');
  document.getElementById('tab-preset').classList.toggle('act',m==='preset');
  document.getElementById('panel-free').style.display=m==='free'?'flex':'none';
  document.getElementById('panel-free').style.flexDirection='column';
  const pp=document.getElementById('panel-preset');
  pp.style.display=m==='preset'?'flex':'none';
  if(m==='preset')pp.style.flexDirection='column';
}

// ── 初始化 ────────────────────────────────────────────────
async function init(){
  const r=await(await fetch('/api/categories')).json();
  const fl=document.getElementById('fl');
  r.levels.forEach(l=>{const o=document.createElement('option');o.value=l;o.text=l;fl.appendChild(o)});
  const fc=document.getElementById('fcat');
  r.super_categories.forEach(c=>{const o=document.createElement('option');o.value=c;o.text=c;fc.appendChild(o)});
  loadGP();
  loadPresets();
}

function dsearch(){clearTimeout(stm);stm=setTimeout(loadGP,250)}

// ── 自由探索：语法点列表 ───────────────────────────────────
async function loadGP(){
  const p=new URLSearchParams();
  const q=document.getElementById('si').value;
  const lv=document.getElementById('fl').value;
  const ct=document.getElementById('fcat').value;
  if(q)p.set('q',q);if(lv)p.set('level',lv);if(ct)p.set('category',ct);
  const r=await(await fetch('/api/grammar_points?'+p)).json();
  rlist(r.items);
}

// 保留旧名兼容
function load(){loadGP()}

function rlist(items){
  document.getElementById('gl').innerHTML=items.map(g=>{
    const s=tgts.has(g.egp_id);
    return '<div class="gi'+(s?' sel':'')+'" onclick="detail(&#39;'+g.egp_id+'&#39;)">'+
      '<div class="gh"><span class="gid">'+g.egp_id+'</span><span class="glv l'+g.level+'">'+g.level+'</span></div>'+
      '<div class="gn">'+(g.name_zh||g.guideword)+'</div>'+
      '<div class="gc">'+g.super_category+' &rsaquo; '+g.sub_category+'</div>'+
      '<button class="ba" onclick="event.stopPropagation();tog(&#39;'+g.egp_id+'&#39;)">'+(s?'&#10003; 已选':'+ 加入目标')+'</button>'+
    '</div>';
  }).join('');
}

function tog(id){tgts.has(id)?tgts.delete(id):tgts.add(id);uui();loadGP()}
function rm(id){tgts.delete(id);uui();loadGP()}
function uui(){
  document.getElementById('tc').textContent='('+tgts.size+')';
  document.getElementById('bg').disabled=tgts.size===0;
  document.getElementById('tl').innerHTML=Array.from(tgts).map(id=>
    '<span class="target-tag">'+id+'<span class="rm" onclick="rm(&#39;'+id+'&#39;)">&times;</span></span>'
  ).join('');
}

async function detail(id){
  const d=await(await fetch('/api/detail/'+id)).json();
  document.getElementById('dt').textContent=d.egp_id+' ['+d.level+']';
  let h='<div class="df"><label>名称</label><div class="val">'+d.name_zh+'</div></div>'+
    '<div class="df"><label>分类</label><div class="val">'+d.super_category+' &rsaquo; '+d.sub_category+'</div></div>'+
    '<div class="df"><label>Guideword</label><div class="val">'+(d.guideword||'-')+'</div></div>'+
    '<div class="df"><label>Can-Do</label><div class="val">'+(d.can_do||'-')+'</div></div>';
  if(d.prerequisites&&d.prerequisites.length){
    h+='<div class="dpr"><h4>&larr; 前置依赖 ('+d.prerequisites.length+')</h4>';
    d.prerequisites.forEach(p=>{
      const b=p.source==='llm_annotation'?'<span class="lb">LLM</span>':'';
      h+='<div class="dpi" onclick="detail(&#39;'+p.egp_id+'&#39;)">'+p.egp_id+' ['+p.level+'] '+p.name_zh+' '+b+'</div>';
    });
    h+='</div>';
  }
  if(d.successors&&d.successors.length){
    h+='<div class="dpr"><h4 style="color:#3498DB">&rarr; 后续节点 ('+d.successors.length+')</h4>';
    d.successors.forEach(s=>{
      h+='<div class="dpi" onclick="detail(&#39;'+s.egp_id+'&#39;)">'+s.egp_id+' ['+s.level+'] '+s.name_zh+'</div>';
    });
    h+='</div>';
  }
  document.getElementById('dc').innerHTML=h;
  document.getElementById('dp').classList.add('act');
}
function cdp(){document.getElementById('dp').classList.remove('act')}

// ── 预设路径 ──────────────────────────────────────────────
async function loadPresets(){
  try{
    const r=await(await fetch('/api/preset_paths')).json();
    const paths=r.paths||[];
    document.getElementById('pl').innerHTML=paths.map(p=>{
      const lvl=p.level_distribution?Object.keys(p.level_distribution).join(' '):'-';
      const tags=Object.keys(p.level_distribution||{}).map(l=>
        '<span class="pt" style="border-color:'+LC[l]+';color:'+LC[l]+'">'+l+' '+p.level_distribution[l]+'</span>'
      ).join('');
      return '<div class="pi-card" id="pc-'+p.path_id+'" onclick="loadPreset(&#39;'+p.path_id+'&#39;)">'+
        '<div class="pn">'+p.name+'</div>'+
        '<div class="pd">'+p.description+'</div>'+
        '<div class="pm">'+tags+'<span class="pt">共 '+p.total_items+' 个</span></div>'+
      '</div>';
    }).join('');
  }catch(e){document.getElementById('pl').innerHTML='<div style="padding:16px;color:#666;font-size:12px">加载失败: '+e.message+'</div>'}
}

async function loadPreset(pid){
  document.querySelectorAll('.pi-card').forEach(el=>el.classList.remove('act'));
  const card=document.getElementById('pc-'+pid);
  if(card)card.classList.add('act');
  curPreset=pid;
  const gc=document.getElementById('gc');
  gc.innerHTML='<div style="text-align:center;padding:60px;color:#888">加载中...</div>';
  try{
    const r=await(await fetch('/api/preset_path/'+pid)).json();
    if(r.error){gc.innerHTML='<div style="text-align:center;padding:60px;color:#E74C3C">'+r.error+'</div>';return}
    renderFlow(gc,r,true);
  }catch(e){gc.innerHTML='<div style="text-align:center;padding:60px;color:#E74C3C">'+e.message+'</div>'}
}

async function compute(){
  if(!tgts.size)return;
  const gc=document.getElementById('gc');
  gc.innerHTML='<div style="text-align:center;padding:60px;color:#888">计算中...</div>';
  try{
    const r=await fetch('/api/shortest_path',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({targets:Array.from(tgts)})});
    const d=await r.json();
    if(d.error){gc.innerHTML='<div style="text-align:center;padding:60px;color:#E74C3C">'+d.error+'</div>';return}
    renderFlow(gc,d);
  }catch(e){gc.innerHTML='<div style="text-align:center;padding:60px;color:#E74C3C">'+e.message+'</div>'}
}

function renderFlow(el,data,isPreset){
  const cross=data.edges.filter(e=>e.source==='llm_annotation').length;
  const lvls=[...new Set(data.nodes.map(n=>n.level))];
  lvls.sort((a,b)=>LO.indexOf(a)-LO.indexOf(b));
  const cats=new Set(data.nodes.map(n=>n.super_category));

  const byLvl={};
  data.nodes.forEach(n=>{(byLvl[n.level]=byLvl[n.level]||[]).push(n)});

  const pm={};
  data.edges.forEach(e=>{
    const to=data.nodes.find(n=>n.id===e.to);
    const fr=data.nodes.find(n=>n.id===e.from);
    if(to&&fr)(pm[to.egp_id]=pm[to.egp_id]||[]).push({egp_id:fr.egp_id,source:e.source});
  });

  let titleRow='';
  if(isPreset&&data.name){
    titleRow='<div class="ptitle">'+data.name+'</div>'+
      (data.description?'<div class="pdesc">'+data.description+'</div>':'');
  }
  let h='<div class="fs-bar">'+titleRow+
    '<span>语法点: <span class="v">'+data.total_steps+'</span></span>'+
    '<span>等级: <span class="v">'+(lvls.length?lvls[0]+' &rarr; '+lvls[lvls.length-1]:'-')+'</span></span>'+
    '<span>大类: <span class="v">'+cats.size+'</span></span>'+
    (cross?'<span>LLM跨类: <span class="v">'+cross+'</span></span>':'')+
  '</div>';

  lvls.forEach(function(lvl,li){
    const c=LC[lvl]||'#3498DB';
    const ns=byLvl[lvl];
    h+='<div class="lvg"><div class="lvl" style="background:'+c+'">'+lvl+'</div><div class="frow">';
    ns.forEach(function(n){
      const t=n.is_target;
      const ps=pm[n.egp_id]||[];
      let ph='';
      if(ps.length){
        const pp=ps.map(function(p){return p.source==='llm_annotation'?'<span class="lm">'+p.egp_id+' [LLM]</span>':p.egp_id});
        ph='<div class="cp">&larr; '+pp.join(', ')+'</div>';
      }
      h+='<div class="fc'+(t?' tgt':'')+'" onclick="detail(&#39;'+n.egp_id+'&#39;)">'+
        '<div class="co">'+(n.order+1)+'</div>'+
        (t?'<div class="ts">&#9733;</div>':'')+
        '<div class="ci">'+n.egp_id+'</div>'+
        '<div class="cn">'+n.name_zh+'</div>'+
        '<div class="cc">'+n.super_category+' &rsaquo; '+n.sub_category+'</div>'+
        (n.guideword?'<div class="gw">'+n.guideword+'</div>':'')+
        ph+
      '</div>';
    });
    h+='</div></div>';
    if(li<lvls.length-1){
      h+='<div class="arw"><svg width="30" height="28"><line x1="15" y1="0" x2="15" y2="20" stroke="#555" stroke-width="2"/><polygon points="8,18 15,28 22,18" fill="#555"/></svg></div>';
    }
  });

  el.innerHTML=h;
}

init();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EGP 学习序列探索器")
    parser.add_argument("--port", type=int, default=5002)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    init_graph()
    print(f"\n  启动路径探索器: http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
