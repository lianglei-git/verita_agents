from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from config import OUTPUT_BASE_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="View score_ranking result files in HTML.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    return parser.parse_args()


def list_level_dirs() -> list[Path]:
    if not OUTPUT_BASE_DIR.exists():
        return []
    return sorted([path for path in OUTPUT_BASE_DIR.iterdir() if path.is_dir()])


def list_phases(level: str) -> list[str]:
    """获取某个级别的所有 phase 目录"""
    level_dir = OUTPUT_BASE_DIR / level
    if not level_dir.exists():
        return []
    phases = [path.name for path in level_dir.iterdir() if path.is_dir() and path.name.startswith("phase")]
    return sorted(phases)


def list_result_files(level: str, phase: str = "phase1") -> list[Path]:
    """获取某个级别和 phase 下的所有结果文件"""
    phase_dir = OUTPUT_BASE_DIR / level / phase
    if not phase_dir.exists():
        return []
    files = [path for path in phase_dir.glob("*.json") if path.is_file()]
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)


def resolve_result_file(level: str, phase: str, file_name: str | None) -> Path | None:
    """根据级别、phase 和文件名解析结果文件路径"""
    files = list_result_files(level, phase)
    if not files:
        return None
    if file_name:
        selected = OUTPUT_BASE_DIR / level / phase / file_name
        if selected.exists():
            return selected
    # 优先查找 latest.json
    latest = OUTPUT_BASE_DIR / level / phase / "latest.json"
    if latest.exists():
        return latest
    # 查找包含 latest 的文件名
    for file_path in files:
        if "latest" in file_path.name:
            return file_path
    return files[0]


def read_result(level: str, phase: str, file_name: str | None) -> tuple[Path | None, dict]:
    """读取结果文件内容"""
    file_path = resolve_result_file(level, phase, file_name)
    if file_path is None:
        return None, {}
    return file_path, json.loads(file_path.read_text(encoding="utf-8"))


def qs_url(level: str, phase: str, file_name: str | None = None) -> str:
    query = {"level": level, "phase": phase}
    if file_name:
        query["file"] = file_name
    return f"/?{urlencode(query)}"


def render_page(level: str, phase: str, file_name: str | None) -> str:
    level_dirs = list_level_dirs()
    levels = [path.name for path in level_dirs]
    if not levels:
        return """<!doctype html><html><body><h1>No output files found.</h1></body></html>"""

    if level not in levels:
        level = levels[0]

    # 获取可用的 phases
    available_phases = list_phases(level)
    if not available_phases:
        return """<!doctype html><html><body><h1>No phase directories found.</h1></body></html>"""
    
    if phase not in available_phases:
        phase = available_phases[0]

    file_path, payload = read_result(level, phase, file_name)
    files = list_result_files(level, phase)
    metadata = payload.get("metadata", {})
    items = payload.get("items", [])

    def level_links_html() -> str:
        return " ".join(
            f'<a href="{html.escape(qs_url(l, phase))}" class="{"current" if l == level else ""}">{html.escape(l)}</a>'
            for l in levels
        )

    def phase_links_html() -> str:
        return " ".join(
            f'<a href="{html.escape(qs_url(level, p))}" class="{"current" if p == phase else ""}">{html.escape(p.upper())}</a>'
            for p in available_phases
        )

    def file_links_html() -> str:
        return " ".join(
            f'<a href="{html.escape(qs_url(level, phase, p.name))}" class="{"current" if file_path and p.name == file_path.name else ""}">{html.escape(p.name)}</a>'
            for p in files
        )

    meta_rows = [
        ("generated_at", metadata.get("generated_at", "")),
        ("level", metadata.get("level", "")),
        ("model", metadata.get("model", "")),
        ("total_items", metadata.get("total_items", "")),
        ("success_count", metadata.get("success_count", "")),
        ("error_count", metadata.get("error_count", "")),
        ("sort_rule", metadata.get("sort_rule", "")),
        ("phase", phase),
        ("plugin", metadata.get("plugin", "")),
    ]
    meta_html = "".join(
        "<tr>"
        f"<th>{html.escape(str(key))}</th>"
        f"<td>{html.escape(str(value))}</td>"
        "</tr>"
        for key, value in meta_rows
    )

    item_rows = []
    for idx, item in enumerate(items, 1):
        info = item.get("egp_info", {})
        # 根据 phase 显示不同的排名
        if phase == "phase2":
            rank = item.get("phase2_rank", idx)
        elif phase == "phase1":
            rank = idx  # phase1 只有原始顺序，没有 phase2_rank
        else:
            rank = idx
            
        egp_id = item.get("egp_id", "")
        score = item.get("llm_score", "")
        chinese = info.get("chinese_human_name", "")
        guideword = info.get("guideword", "")
        can_do = info.get("can_do", "")
        ex_raw = info.get("examples", "") or ""
        example = ex_raw.split("、")[0].strip() if ex_raw else ""
        reason = item.get("score_reason", "") or item.get("tie_break_reason", "")
        orig_rank = item.get("original_rank")
        p2_rank = item.get("phase2_rank")
        position_changed = (
            orig_rank is not None and p2_rank is not None and int(orig_rank) != int(p2_rank)
        )
        row_class = " phase2-changed" if position_changed and phase == "phase2" else ""
        item_rows.append(
            f"<tr class='{row_class.strip()}'>"
            f"<td class='col-rank'>{html.escape(str(rank))}</td>"
            f"<td class='col-id'>{html.escape(str(egp_id))}</td>"
            f"<td class='col-score'><span class='score-pill'>{html.escape(str(score))}</span></td>"
            f"<td class='col-cn'>{html.escape(chinese)}</td>"
            f"<td class='col-guide'>{html.escape(guideword)}</td>"
            f"<td class='col-cando'>{html.escape(can_do)}</td>"
            f"<td class='col-ex'>{html.escape(example)}</td>"
            f"<td class='col-reason'>{html.escape(reason)}</td>"
            "</tr>"
        )
    items_table_body = "".join(item_rows)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EGP Score Viewer · {html.escape(level)}</title>
  <style>
    :root {{
      --bg: #f5f6f8;
      --surface: #fff;
      --text: #1e293b;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --current: #0f172a;
      --row-hover: #f1f5f9;
      --score-low: #0d9488;
      --score-mid: #ca8a04;
      --score-high: #9333ea;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 20px 24px 48px;
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      font-size: 15px;
      line-height: 1.55;
      color: var(--text);
      background: var(--bg);
    }}
    .wrap {{
      max-width: 1600px;
      margin: 0 auto;
    }}
    h1 {{
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--current);
      margin: 0 0 16px 0;
    }}
    .nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 16px;
      align-items: baseline;
      margin-bottom: 20px;
      padding: 14px 18px;
      background: var(--surface);
      border-radius: 10px;
      border: 1px solid var(--border);
    }}
    .nav-label {{
      color: var(--text-muted);
      font-size: 0.875rem;
      font-weight: 500;
    }}
    .nav a {{
      color: var(--accent);
      text-decoration: none;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.9rem;
    }}
    .nav a:hover {{
      background: var(--row-hover);
      color: var(--accent-hover);
    }}
    .nav a.current {{
      background: var(--accent);
      color: #fff;
      font-weight: 500;
    }}
    .current-file {{
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 8px;
      word-break: break-all;
    }}
    .meta-card {{
      background: var(--surface);
      border-radius: 10px;
      border: 1px solid var(--border);
      margin-bottom: 24px;
      overflow: hidden;
    }}
    .meta-card h2 {{
      margin: 0;
      padding: 12px 18px;
      font-size: 1rem;
      font-weight: 600;
      background: var(--row-hover);
      border-bottom: 1px solid var(--border);
    }}
    .meta-card table {{
      width: 100%;
      border-collapse: collapse;
    }}
    .meta-card th {{
      width: 140px;
      padding: 10px 18px;
      text-align: left;
      font-weight: 500;
      color: var(--text-muted);
      font-size: 0.875rem;
      border-bottom: 1px solid var(--border);
    }}
    .meta-card td {{
      padding: 10px 18px;
      border-bottom: 1px solid var(--border);
      word-break: break-word;
    }}
    .meta-card tr:last-child th, .meta-card tr:last-child td {{
      border-bottom: none;
    }}
    .items-card {{
      background: var(--surface);
      border-radius: 10px;
      border: 1px solid var(--border);
      overflow: hidden;
    }}
    .items-card h2 {{
      margin: 0;
      padding: 12px 18px;
      font-size: 1rem;
      font-weight: 600;
      background: var(--row-hover);
      border-bottom: 1px solid var(--border);
    }}
    .items-scroll {{
      overflow-x: auto;
    }}
    .items-table {{
      width: 100%;
      min-width: 900px;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    .items-table th {{
      padding: 12px 14px;
      text-align: left;
      font-weight: 600;
      color: var(--text-muted);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      background: var(--row-hover);
      border-bottom: 2px solid var(--border);
      white-space: nowrap;
    }}
    .items-table td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    .items-table tbody tr:hover {{
      background: var(--row-hover);
    }}
    .col-rank {{ width: 56px; text-align: right; font-variant-numeric: tabular-nums; color: var(--text-muted); }}
    .col-id {{ width: 100px; font-family: ui-monospace, monospace; font-size: 0.85rem; }}
    .col-score {{ width: 72px; }}
    .col-cn {{ min-width: 140px; font-weight: 500; color: var(--current); }}
    .col-guide {{ min-width: 180px; max-width: 260px; }}
    .col-cando {{ min-width: 200px; max-width: 320px; }}
    .col-ex {{ min-width: 180px; max-width: 280px; font-style: italic; color: var(--text-muted); }}
    .col-reason {{ min-width: 100px; max-width: 180px; font-size: 0.85rem; color: var(--text-muted); }}
    .score-pill {{
      display: inline-block;
      min-width: 2.2em;
      padding: 4px 8px;
      border-radius: 6px;
      font-variant-numeric: tabular-nums;
      font-weight: 600;
      font-size: 0.9rem;
      text-align: center;
    }}
    .score-pill.low {{ background: #ccfbf1; color: var(--score-low); }}
    .score-pill.mid {{ background: #fef9c3; color: #a16207; }}
    .score-pill.high {{ background: #f3e8ff; color: var(--score-high); }}
    .legend {{ font-weight: normal; color: var(--text-muted); font-size: 0.85rem; }}
    tr.phase2-changed {{
      background: #fef3c7;
      border-left: 3px solid #f59e0b;
    }}
    tr.phase2-changed:hover {{
      background: #fde68a;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>EGP 学习路径 · Score Viewer</h1>
    <nav class="nav">
      <span class="nav-label">Level:</span>
      {level_links_html()}
      <span class="nav-label" style="margin-left:8px">Phase:</span>
      {phase_links_html()}
      <span class="nav-label" style="margin-left:8px">File:</span>
      {file_links_html()}
    </nav>
    <p class="current-file">当前文件: {html.escape(str(file_path) if file_path else "—")}</p>

    <section class="meta-card">
      <h2>Metadata</h2>
      <table>
        <tbody>
          {meta_html}
        </tbody>
      </table>
    </section>

    <section class="items-card">
      <h2>Items · 共 {len(items)} 条 <span class="legend">（{phase.upper()} · 黄底橙边 = Phase2 已调整顺序）</span></h2>
      <div class="items-scroll">
        <table class="items-table">
          <thead>
            <tr>
              <th class="col-rank">#</th>
              <th class="col-id">EGP ID</th>
              <th class="col-score">Score</th>
              <th class="col-cn">中文名</th>
              <th class="col-guide">Guideword</th>
              <th class="col-cando">Can-do</th>
              <th class="col-ex">Example</th>
              <th class="col-reason">Reason</th>
            </tr>
          </thead>
          <tbody>
            {items_table_body}
          </tbody>
        </table>
      </div>
    </section>
  </div>
  <script>
    (function() {{
      var scoreCells = document.querySelectorAll('.col-score .score-pill');
      scoreCells.forEach(function(el) {{
        var n = parseFloat(el.textContent);
        if (!isNaN(n)) {{
          el.classList.add(n <= 33 ? 'low' : n <= 66 ? 'mid' : 'high');
        }}
      }});
    }})();
  </script>
</body>
</html>"""


class ViewerHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        level = params.get("level", ["A1"])[0]
        phase = params.get("phase", ["phase1"])[0]
        file_name = params.get("file", [None])[0]

        content = render_page(level, phase, file_name).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ViewerHandler)
    print(f"Viewer running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
