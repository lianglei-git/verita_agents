"""
Phase 3: 学习路径校验（Path Check）

对 Phase1/Phase2 产出的学习路径进行抽样，由 LLM 判断抽样片段是否符合「螺旋学习路径」描述，
输出置信度与问题列表，并生成 MD 格式的评分报告。置信度 > 0.85 时不触发警报。
"""
from __future__ import annotations

import argparse
import importlib
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import CEFR_LEVELS, get_config
from llm_client import LLMClient

if importlib.util.find_spec("dotenv"):
    importlib.import_module("dotenv").load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("phase3_path_check")

# 抽样次数与每次条数
NUM_SAMPLES = 3
SAMPLE_SIZE = 20
CONFIDENCE_ALERT_THRESHOLD = 0.85


def normalize_max_tokens_for_model(model: str, configured_max_tokens: int) -> int:
    """Avoid invalid max_tokens for models with smaller output limits."""
    name = (model or "").strip().lower()
    if "deepseek-chat" in name:
        return min(configured_max_tokens, 8192)
    if "deepseek-reasoner" in name:
        return min(configured_max_tokens, 64000)
    return configured_max_tokens

CHECK_RESPONSE_SCHEMA = {
    "confidence": "0~1 的浮点数，表示整体上该学习路径符合上述描述的程度",
    "issues": [
        {
            "segment_label": "第几次抽样的片段，如「第1次抽取」",
            "position_or_id": "出问题的位置说明（如 rank 范围或 egp_id）",
            "description": "中文，简要说明何处不符合、为何不符合",
            "suggestion": "中文，可选的改进建议",
        }
    ],
    "overall_reason": "中文，整体说明为何给出该置信度，以及路径的优缺点概括",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase3: 学习路径抽样校验，输出置信度与 MD 评分报告。",
    )
    parser.add_argument("--level", choices=list(CEFR_LEVELS), default="A1", help="CEFR level")
    parser.add_argument("--lang", default="en", help="Language code")
    parser.add_argument(
        "--input",
        default=None,
        help="学习路径 JSON（默认先尝试 phase2_same_score_latest.json，不存在则用 latest.json）",
    )
    parser.add_argument("--model", default=None, help="Override LLM model")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for sampling (reproducibility)")
    parser.add_argument(
        "--samples",
        type=int,
        default=NUM_SAMPLES,
        help=f"抽样次数 (default {NUM_SAMPLES})",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=SAMPLE_SIZE,
        help=f"每次抽样条数 (default {SAMPLE_SIZE})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=CONFIDENCE_ALERT_THRESHOLD,
        help=f"置信度低于此值则警报 (default {CONFIDENCE_ALERT_THRESHOLD})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry run模式，不实际调用API")
    parser.add_argument("--force-rerun", action="store_true", help="强制重新运行，忽略缓存")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_path_document(cfg, input_path: Path | None) -> tuple[dict[str, Any], Path]:
    """加载学习路径：支持多种可能的输入源"""
    if input_path is not None:
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        doc = load_json(path)
        return doc, path

    # 自动探测可能的路径文件
    possible_files = [
        cfg.output_dir / "phase2" / "same_score_ordered_latest.json",  # 新的Phase 2输出路径
        cfg.output_dir / "phase2" / "same_score_ordered.json",  # 新的Phase 2输出路径
        cfg.output_dir / "phase2_same_score_latest.json",  # 旧的Phase 2输出路径
        cfg.output_dir / "latest.json",
        cfg.output_dir / "phase1" / "scored_items.json",
        cfg.output_dir / "phase1" / "full_sort_latest.json",
    ]
    for path in possible_files:
        if path.exists():
            return load_json(path), path

    raise FileNotFoundError(
        f"No path file found in {cfg.output_dir}. "
        f"Provide --input or ensure one of the following exists: {', '.join(str(p) for p in possible_files)}."
    )


def get_item_rank(item: dict[str, Any]) -> int:
    """用于排序与展示的 rank：优先 phase2_rank，否则 rank。"""
    r = item.get("phase2_rank") or item.get("rank")
    if r is not None:
        return int(r)
    return 0


def build_segment_payload(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建单段抽样的精简 payload，供 LLM 判断。"""
    payload = []
    for i, item in enumerate(items):
        rank = get_item_rank(item)
        info = item.get("egp_info") or {}
        examples = (info.get("examples") or "").strip()
        first_ex = (examples.split("、")[0].strip() if examples else "")[:80]
        payload.append({
            # "rank": rank,
            "egp_id": item.get("egp_id", ""),
            # "llm_score": item.get("llm_score"),
            "guideword": (info.get("guideword") or "").strip()[:120],
            "can_do": (info.get("can_do") or "").strip()[:150],
            "category": (info.get("category") or "").strip()[:80],
            "example": first_ex,
        })
    return payload


def draw_sample_starts(total: int, sample_size: int, num_samples: int, seed: int | None) -> list[int]:
    """在 [0, total - sample_size] 内随机抽取 num_samples 个起始下标（可重复）。"""
    if total < sample_size:
        return []
    max_start = total - sample_size
    rng = random.Random(seed)
    return [rng.randint(0, max_start) for _ in range(num_samples)]


def build_check_prompt(
    fixed_prompt: str,
    level: str,
    segments: list[tuple[str, list[dict[str, Any]]]],
) -> str:
    """组装校验 prompt：固定描述 + 任务说明 + 各段数据。"""
    task = (
        "你的任务：判断以下「学习路径抽样数据」是否符合上述描述。\n\n"
        "重要约定：每段抽样数据应视为「以第一条为起点的学习路径」。即：只评估该段内从第一条到最后一条的递进是否合理、是否符合螺旋/先简后复等原则；不要考虑第一条之前是否还有其它学习内容，不要管第一条数据之前的学习路径。\n\n"
        "请从螺旋递进、先简后复、模块顺序等角度评估这一段；若段内条目顺序或内容与描述不一致，请在 issues 中列出。\n\n"
        "返回内容须包含：\n"
        "1. confidence：整体置信度，0~1 的浮点数，表示该段路径符合上述描述的程度。\n"
        "2. issues：若有不符合之处，列出 segment_label、position_or_id、description、suggestion。若无则可为空数组。\n"
        "3. overall_reason：整体说明为何给出该置信度，并简要概括该段路径的优缺点。\n\n"
        "请严格输出 JSON，不要输出额外文本。"
    )
    schema_str = json.dumps(CHECK_RESPONSE_SCHEMA, ensure_ascii=False, indent=2)
    parts = [f"## 固定描述（螺旋学习路径）\n{fixed_prompt}\n\n## 任务与输出格式\n{task}\n\n输出 JSON 格式：\n{schema_str}\n\n当前等级：{level}\n"]
    for label, payload in segments:
        parts.append(f"## {label}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n\n")
    return "\n".join(parts)


def normalize_confidence(raw: Any) -> float:
    """将 LLM 返回的 confidence 规范到 [0, 1]。"""
    if isinstance(raw, (int, float)):
        return max(0.0, min(1.0, float(raw)))
    s = str(raw).strip()
    try:
        return max(0.0, min(1.0, float(s)))
    except ValueError:
        return 0.0


def normalize_issues(raw: Any) -> list[dict[str, Any]]:
    """解析 issues 列表。"""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append({
            "segment_label": str(item.get("segment_label", "")).strip(),
            "position_or_id": str(item.get("position_or_id", "")).strip(),
            "description": str(item.get("description", "")).strip(),
            "suggestion": str(item.get("suggestion", "")).strip(),
        })
    return out


def run_check(
    llm: LLMClient,
    cfg,
    path_doc: dict[str, Any],
    segments: list[tuple[str, list[dict[str, Any]]]],
    level: str,
) -> dict[str, Any]:
    """调用 LLM 做一次路径校验，返回解析后的结果。"""
    fixed_prompt = cfg.phase1._read_phase0_output_prompt()
    prompt = build_check_prompt(fixed_prompt, level, segments)
    print(prompt)
    system = "你是一名精通二语习得与 CEFR 的评估专家，只输出要求的 JSON，不输出其他内容。"
    raw = llm.chat_json(prompt, system)
    confidence = normalize_confidence(raw.get("confidence"))
    issues = normalize_issues(raw.get("issues"))
    overall_reason = str(raw.get("overall_reason", "")).strip()
    return {
        "confidence": confidence,
        "issues": issues,
        "overall_reason": overall_reason,
        "raw_response": raw,
        "llm_prompt": prompt,
    }


def write_md_report(
    output_path: Path,
    level: str,
    source_path: Path,
    source_meta: dict[str, Any],
    segments_info: list[dict[str, Any]],
    result: dict[str, Any],
    threshold: float,
    run_started_at: str,
    total_items: int,
) -> None:
    """生成并写入 MD 格式的评分报告。"""
    confidence = result["confidence"]
    issues = result.get("issues") or []
    overall_reason = result.get("overall_reason", "")
    alert = confidence < threshold

    lines = [
        "# 学习路径校验报告 (Phase 3)",
        "",
        f"- **等级**：{level}",
        f"- **数据来源**：`{source_path.name}`",
        f"- **路径总条数**：{total_items}",
        f"- **校验时间**：{run_started_at}",
        f"- **抽样说明**：共 {len(segments_info)} 段，每段 {segments_info[0].get('size', 20) if segments_info else 20} 条（随机起始位置，以该段第一条为路径起点）",
        "",
        "---",
        "",
        "## 1. 整体置信度",
        "",
        f"**{confidence:.2%}**",
        "",
    ]
    if alert:
        lines.extend([
            f"⚠️ **警报**：置信度低于设定阈值 {threshold:.0%}，建议人工复核路径与 prompt 设计。",
            "",
        ])
    else:
        lines.extend([
            f"✅ 置信度 ≥ {threshold:.0%}，未触发警报。",
            "",
        ])

    lines.extend([
        "## 2. 整体评价",
        "",
        overall_reason or "（无）",
        "",
        "---",
        "",
        "## 3. 问题与建议",
        "",
    ])
    if not issues:
        lines.append("未列出具体问题。")
    else:
        for i, issue in enumerate(issues, 1):
            seg = issue.get("segment_label", "")
            pos = issue.get("position_or_id", "")
            desc = issue.get("description", "")
            sug = issue.get("suggestion", "")
            lines.append(f"### 问题 {i}")
            lines.append(f"- **片段**：{seg}")
            lines.append(f"- **位置/ID**：{pos}")
            lines.append(f"- **说明**：{desc}")
            if sug:
                lines.append(f"- **建议**：{sug}")
            lines.append("")

    if alert:
        lines.extend([
            "---",
            "",
            "## 置信度偏低时的建议操作",
            "",
            "1. **优化 Phase1 打分 prompt**：在 `config.py` 的 `fixed_prompt` 中已强调「同一语法范畴的条目落在相近分数区间」，可重新跑 Phase1 生成新路径后再校验。",
            "2. **按报告中的 issues 调整**：根据上述「问题与建议」调整等级对应的 `LLM_Prompt_Score_Config`（如明确各分数段对应的语法模块），使 LLM 打分更按模块聚集。",
            "3. **后处理按模块聚类（可选）**：在 Phase1 之后、Phase2 之前增加一步：按 `egp_info.category` 等分组，组内按 `llm_score` 排序，再按预设模块顺序拼接，可减少范畴穿插。",
            "4. **若当前路径已可接受**：可将 Phase3 的 `--threshold` 调低（如 0.70）仅作参考，或忽略警报、以报告中的具体建议为迭代依据。",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## 4. 抽样信息",
        "",
    ])
    for seg_info in segments_info:
        lines.append(f"- **{seg_info['label']}**：起始 rank {seg_info.get('start_rank')}，共 {seg_info.get('size')} 条")
    lines.append("")

    lines.extend([
        "---",
        "",
        "## 5. 元数据",
        "",
        f"- 数据源路径：`{source_path}`",
        "",
    ])
    if source_meta:
        lines.append("来源文件 metadata 摘要：")
        for k, v in list(source_meta.items())[:15]:
            lines.append(f"- {k}: {v}")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def dry_run_phase3(cfg, path_doc, resolved_path, segments, segments_info, result_path: Path, latest_path: Path) -> None:
    """模拟Phase 3的学习路径校验过程"""
    logger.info("Dry run模式 - 模拟Phase 3学习路径校验过程")
    
    # 模拟评估结果
    total_items = len(path_doc.get("items", []))
    
    # 模拟置信度
    confidence = random.uniform(0.8, 0.95)  # 模拟在0.8-0.95之间的高置信度
    
    # 模拟生成报告
    with open(result_path, 'w', encoding='utf-8') as f:
        f.write(f"# Phase 3 学习路径校验报告 - Dry Run模式\n\n")
        f.write(f"**生成时间**: {datetime.now(timezone.utc).astimezone().isoformat()}\n")
        f.write(f"**等级**: {cfg.level}\n")
        f.write(f"**置信度**: {confidence:.3f}\n")
        f.write(f"**抽样评估**: 通过模拟评估，路径质量良好\n")
        f.write(f"**总条目数**: {total_items}\n\n")
        f.write("## 备注\n")
        f.write("此为Dry Run模式生成的模拟报告，所有评估结果均为模拟数据。\n")
    
    # 复制到latest文件
    with open(latest_path, 'w', encoding='utf-8') as f:
        f.write(f"# Phase 3 学习路径校验报告 - Dry Run模式\n\n")
        f.write(f"**生成时间**: {datetime.now(timezone.utc).astimezone().isoformat()}\n")
        f.write(f"**等级**: {cfg.level}\n")
        f.write(f"**置信度**: {confidence:.3f}\n")
        f.write(f"**抽样评估**: 通过模拟评估，路径质量良好\n\n")
        f.write("**重要提示**: 此为Dry Run模式生成的模拟报告。\n")


def main() -> None:
    args = parse_args()
    cfg = get_config(level=args.level, lang=args.lang)
    
    # 检查缓存
    cache_dir = Path("output") / args.level / "phase3"
    cache_file = cache_dir / "path_check_report.md"
    
    if not args.force_rerun and cache_file.exists():
        logger.info(f"使用缓存文件: {cache_file}")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"✓ Phase 3 已完成 (使用缓存)，报告大小: {len(content)}字符")
            return
        except Exception as e:
            logger.warning(f"缓存文件读取失败: {e}")

    if args.model:
        cfg.llm.model = args.model
    cfg.llm.max_tokens = normalize_max_tokens_for_model(cfg.llm.model, cfg.llm.max_tokens)
    logger.info("Using model=%s, max_tokens=%s", cfg.llm.model, cfg.llm.max_tokens)

    if not cfg.llm.api_key and not args.dry_run:
        logger.error("OPENAI_API_KEY is not set")
        sys.exit(1)

    run_started_at = datetime.now(timezone.utc).astimezone().isoformat()
    input_path = Path(args.input) if args.input else None
    path_doc, resolved_path = load_path_document(cfg, input_path)
    items = path_doc.get("items", [])
    total = len(items)
    sample_size = max(1, min(args.sample_size, total))
    num_samples = max(1, args.samples)

    if total < sample_size:
        logger.error("Path has %s items, need at least %s for one sample", total, sample_size)
        sys.exit(1)

    # 确定随机起点
    starts = draw_sample_starts(total, sample_size, num_samples, args.seed)
    if not starts:
        logger.error("No sample starts generated")
        sys.exit(1)

    # 构建各段
    segments: list[tuple[str, list[dict[str, Any]]]] = []
    segments_info: list[dict[str, Any]] = []
    for idx, start in enumerate(starts):
        segment_items = items[start : start + sample_size]
        label = f"第{idx + 1}次抽取（rank {get_item_rank(segment_items[0])} 起，共 {len(segment_items)} 条）"
        payload = build_segment_payload(segment_items)
        segments.append((label, payload))
        segments_info.append({
            "label": label,
            "start_index": start,
            "start_rank": get_item_rank(segment_items[0]),
            "size": len(segment_items),
        })

    logger.info("Loaded %s items from %s", total, resolved_path)
    logger.info("Sampled %s segments (size=%s), seed=%s", num_samples, sample_size, args.seed)

    # Dry run模式处理 - 先检查是否需要创建模拟输入文件
    if args.dry_run:
        logger.info("Phase 3 Dry run模式启动")
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 如果输入文件不存在，创建模拟的Phase 2输出文件
        if not resolved_path.exists():
            logger.info("未找到Phase 2输出文件，创建模拟数据")
            phase2_cache_dir = Path("output") / args.level / "phase2"
            phase2_cache_file = phase2_cache_dir / "same_score_ordered.json"
            
            if not phase2_cache_file.exists():
                # 创建模拟的Phase 2输出
                phase2_cache_dir.mkdir(parents=True, exist_ok=True)
                simulated_items = []
                for i in range(50):  # 模拟50个条目
                    simulated_items.append({
                        "egp_id": f"GG-{i+1:03d}",
                        "llm_score": float(20 + i * 1.5),  # 模拟分数递增
                        "rank": i + 1,
                        "phase2_rank": i + 1,
                        "status": "ok",
                        "egp_info": {
                            "guideword": f"模拟语法点{i+1}",
                            "can_do": f"模拟能力描述{i+1}",
                            "category": "grammar",
                            "examples": f"示例{i+1}、示例{i+1}-2"
                        }
                    })
                
                simulated_doc = {
                    "metadata": {
                        "level": args.level,
                        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
                        "mode": "dry_run_simulated",
                        "total_items": len(simulated_items)
                    },
                    "items": simulated_items
                }
                
                with open(phase2_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(simulated_doc, f, ensure_ascii=False, indent=2)
                logger.info("已创建模拟Phase 2数据: %s", phase2_cache_file)
                
                # 重新加载路径文件
                path_doc, resolved_path = load_path_document(cfg, phase2_cache_file)
            else:
                # 如果已有缓存文件，使用它
                path_doc, resolved_path = load_path_document(cfg, phase2_cache_file)
        
        # 重新构建分段数据（因为path_doc可能已更新）
        items = path_doc.get("items", [])
        total = len(items)
        sample_size = max(1, min(args.sample_size, total))
        num_samples = max(1, args.samples)
        
        if total < sample_size:
            logger.warning("路径数据不足，使用全部数据作为样本")
            sample_size = total
            num_samples = 1
        
        starts = draw_sample_starts(total, sample_size, num_samples, args.seed)
        if not starts:
            logger.warning("无法生成样本起始点，使用默认配置")
            starts = [0] if total > 0 else []
        
        segments = []
        segments_info = []
        for idx, start in enumerate(starts):
            if start + sample_size > total:
                sample_size = total - start
            segment_items = items[start: start + sample_size]
            label = f"第{idx + 1}次抽取（rank {get_item_rank(segment_items[0])} 起，共 {len(segment_items)} 条）"
            payload = build_segment_payload(segment_items)
            segments.append((label, payload))
            segments_info.append({
                "label": label,
                "start_index": start,
                "start_rank": get_item_rank(segment_items[0]),
                "size": len(segment_items),
            })
        
        logger.info("重新构建了%d个样本段，每段%d条", len(segments), sample_size)
        
        # 创建结果路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_path = cache_dir / f"path_check_report_{timestamp}.md"
        latest_path = cache_dir / "path_check_report.md"
        
        dry_run_phase3(cfg, path_doc, resolved_path, segments, segments_info, result_path, latest_path)
        
        logger.info("✓ Phase 3 Dry run完成")
        logger.info("生成的文件:")
        logger.info("  - %s", result_path)
        logger.info("  - %s", latest_path)
        return

    # 确保缓存目录存在
    cache_dir.mkdir(parents=True, exist_ok=True)

    llm = LLMClient(cfg.llm)
    result = run_check(llm, cfg, path_doc, segments, args.level)
    confidence = result["confidence"]
    logger.info("Check confidence: %.2f (threshold=%.2f)", confidence, args.threshold)
    if confidence < args.threshold:
        logger.warning("Confidence below threshold: alert")

    # 输出 MD 报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 同时保存到缓存目录
    cache_report_path = cache_dir / f"path_check_report_{timestamp}.md" 
    cache_latest_path = cache_dir / "path_check_report.md"
    
    source_meta = path_doc.get("metadata") or {}
 # 保存到缓存
    write_md_report(
        cache_report_path,
        args.level,
        resolved_path,
        source_meta,
        segments_info,
        result,
        args.threshold,
        run_started_at,
        total,
    )
    write_md_report(
        cache_latest_path,
        args.level,
        resolved_path,
        source_meta,
        segments_info,
        result,
        args.threshold,
        run_started_at,
        total,
    )

    logger.info("Report written: %s", cache_report_path)
    logger.info("Cached report: %s", cache_latest_path)


if __name__ == "__main__":
    main()
