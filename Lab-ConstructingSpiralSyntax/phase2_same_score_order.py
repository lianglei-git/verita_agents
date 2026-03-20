from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import CEFR_LEVELS, get_config
from llm_client import LLMClient

dotenv = importlib.import_module("dotenv") if importlib.util.find_spec("dotenv") else None
if dotenv is not None:
    dotenv.load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("phase2_same_score_order")

GROUP_RESPONSE_SCHEMA = {
    "ordered_ids": ["按更早到更晚排序后的 egp_id 列表"],
    "reasons": [
        {"egp_id": "GG-XXX", "reason": "中文，说明该条目为什么在这一组里更早或更晚"}
    ],
    "group_summary": "中文，概述这一组的螺旋学习排序逻辑",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve same-score groups with LLM spiral ordering.",
    )
    parser.add_argument("--level", choices=list(CEFR_LEVELS), default="A1", help="CEFR level")
    parser.add_argument("--lang", default="en", help="Language code (default: en)")
    parser.add_argument("--input", default=None, help="Step1 result path, default: output/<level>/latest.json")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use LLM for same-score group ordering (default: no-LLM, sort by EGP id trailing number)",
    )
    parser.add_argument("--model", default=None, help="Override LLM model name")
    parser.add_argument("--sleep", type=float, default=2.0, help="Sleep seconds between LLM calls")
    parser.add_argument("--resume", action="store_true", help="Resume from phase2_same_score_latest.json")
    parser.add_argument("--limit-groups", type=int, default=None, help="Only process first N duplicate-score groups")
    parser.add_argument("--rate-limit-wait", type=float, default=20.0, help="Base wait seconds on rate limit")
    parser.add_argument("--max-rate-limit-wait", type=float, default=180.0, help="Max wait seconds on rate limit")
    parser.add_argument("--max-group-retries", type=int, default=10, help="Max retries per same-score group")
    parser.add_argument("--dry-run", action="store_true", help="Dry run模式，不实际调用API")
    parser.add_argument("--force-rerun", action="store_true", help="强制重新运行，忽略缓存")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "too many requests" in text or "rate limit" in text or "429" in text


def load_source_document(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data.get("items"), list):
        raise ValueError(f"Invalid source file, missing items list: {path}")
    return data


def build_group_prompt(cfg, level: str, score_value: float | int | str, items: list[dict[str, Any]]) -> str:
    group_payload = []
    for item in items:
        info = item.get("egp_info", {})
        examples = str(info.get("examples", "")).split("、")
        example = next((part.strip() for part in examples if part.strip()), "")
        group_payload.append(
            {
                "egp_id": item.get("egp_id", ""),
                "guideword": info.get("guideword", ""),
                "can_do": info.get("can_do", ""),
                "category": info.get("category", ""),
                "chinese_human_name": info.get("chinese_human_name", ""),
                "example": example,
                "step1_score": item.get("llm_score"),
                "step1_rank": item.get("rank"),
            }
        )

    return (
        f"{cfg.phase1.fixed_prompt}\n\n"
        "现在进入第二步：同分组内排序。\n"
        f"以下语法点在第一步中拿到了相同分数 `{score_value}`，请不要重新打分，而是只对这一组做组内螺旋学习排序。\n"
        "你的目标是判断：在这些已经同分的语法点里，谁应该更早学、谁应该更晚学。\n\n"
        "排序原则：\n"
        "1. 优先更基础、前置依赖更少、迁移性更强、表达频率更高的语法点。\n"
        "2. 若两个语法点非常接近，也必须给出稳定顺序。\n"
        "3. ordered_ids 必须包含且只包含本组全部 egp_id，顺序从更早到更晚。\n"
        "4. reasons 需要给每个 egp_id 一条中文说明。\n"
        "5. 严格输出 JSON，不要输出额外文本。\n\n"
        f"输出 JSON 格式：\n{json.dumps(GROUP_RESPONSE_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        f"当前等级：{level}\n"
        f"同分组数据：\n{json.dumps(group_payload, ensure_ascii=False, indent=2)}"
    )


def normalize_ordered_ids(raw_ids: Any, expected_ids: list[str]) -> list[str]:
    if not isinstance(raw_ids, list):
        raise ValueError("ordered_ids is not a list")
    expected_set = set(expected_ids)
    ordered_ids: list[str] = []
    seen: set[str] = set()
    for value in raw_ids:
        item_id = str(value).strip()
        if item_id in expected_set and item_id not in seen:
            ordered_ids.append(item_id)
            seen.add(item_id)
    for item_id in expected_ids:
        if item_id not in seen:
            ordered_ids.append(item_id)
    return ordered_ids


def extract_egp_trailing_number(egp_id: str) -> int:
    """从 EGP id 截取末尾数字用于排序，例如 egp-a2-093 -> 93。"""
    s = str(egp_id).strip()
    if not s:
        return 0
    parts = s.split("-")
    if not parts:
        return 0
    try:
        return int(parts[-1])
    except (ValueError, TypeError):
        return 0


def resolve_group_order_no_llm(items: list[dict[str, Any]]) -> dict[str, Any]:
    """无 LLM 模式：按 EGP id 末尾数字升序对同分组排序。"""
    sorted_items = sorted(items, key=lambda item: extract_egp_trailing_number(item.get("egp_id", "")))
    ordered_ids = [str(item.get("egp_id", "")).strip() for item in sorted_items]
    return {
        "status": "no_llm",
        "ordered_ids": ordered_ids,
        "reason_map": {},
        "group_summary": "无LLM模式：按 EGP id 末尾数字升序",
        "llm_prompt": None,
        "llm_call_started_at": None,
        "llm_call_finished_at": None,
    }


def normalize_reason_map(raw_reasons: Any) -> dict[str, str]:
    reason_map: dict[str, str] = {}
    if isinstance(raw_reasons, dict):
        for key, value in raw_reasons.items():
            reason_map[str(key).strip()] = str(value).strip()
        return reason_map
    if isinstance(raw_reasons, list):
        for item in raw_reasons:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("egp_id", "")).strip()
            if not item_id:
                continue
            reason_map[item_id] = str(item.get("reason", "")).strip()
    return reason_map


def resolve_group_order(
    llm: LLMClient,
    cfg,
    level: str,
    score_value: float | int | str,
    items: list[dict[str, Any]],
    max_group_retries: int,
    rate_limit_wait: float,
    max_rate_limit_wait: float,
) -> dict[str, Any]:
    prompt = build_group_prompt(cfg, level, score_value, items)
    first_started_at: str | None = None
    last_finished_at: str | None = None
    last_error: Exception | None = None
    expected_ids = [str(item.get("egp_id", "")).strip() for item in items]

    for attempt in range(max_group_retries):
        started_at = datetime.now(timezone.utc).astimezone().isoformat()
        if first_started_at is None:
            first_started_at = started_at
        try:
            response = llm.chat_json(prompt, cfg.phase1.fixed_prompt)
            last_finished_at = datetime.now(timezone.utc).astimezone().isoformat()
            ordered_ids = normalize_ordered_ids(response.get("ordered_ids"), expected_ids)
            reason_map = normalize_reason_map(response.get("reasons"))
            group_summary = str(response.get("group_summary", "")).strip()
            return {
                "status": "ok",
                "ordered_ids": ordered_ids,
                "reason_map": reason_map,
                "group_summary": group_summary,
                "llm_prompt": prompt,
                "llm_call_started_at": first_started_at,
                "llm_call_finished_at": last_finished_at,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            last_finished_at = datetime.now(timezone.utc).astimezone().isoformat()
            logger.warning("Tie-break failed for score %s (attempt %s): %s", score_value, attempt + 1, exc)
            if _is_rate_limit_error(exc) and attempt < max_group_retries - 1:
                wait_seconds = min(rate_limit_wait * (2 ** attempt), max_rate_limit_wait)
                logger.warning("Rate limit on score %s, sleep %.1fs then retry", score_value, wait_seconds)
                time.sleep(wait_seconds)
                continue
            if attempt < max_group_retries - 1:
                time.sleep(cfg.llm.retry_delay)

    logger.error("Tie-break fallback for score %s: %s", score_value, last_error)
    return {
        "status": "error",
        "ordered_ids": expected_ids,
        "reason_map": {},
        "group_summary": f"LLM 组内排序失败，保留原始顺序。错误：{last_error}",
        "llm_prompt": prompt,
        "llm_call_started_at": first_started_at,
        "llm_call_finished_at": last_finished_at,
    }


def build_working_items(source_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    working_items: list[dict[str, Any]] = []
    for index, item in enumerate(source_items, start=1):
        cloned = deepcopy(item)
        cloned["original_rank"] = int(item.get("rank", index) or index)
        cloned["tie_group_score"] = item.get("llm_score")
        cloned["tie_group_size"] = 1
        cloned["tie_group_order"] = 1
        cloned["tie_break_reason"] = ""
        cloned["tie_break_group_summary"] = ""
        cloned["phase2_status"] = "pending"
        working_items.append(cloned)
    return working_items


def group_same_scores(items: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = str(item.get("llm_score"))
        groups.setdefault(key, []).append(item)
    ordered = sorted(groups.items(), key=lambda pair: (float(pair[0]), min(it.get("original_rank", 10**9) for it in pair[1])))
    return ordered


def apply_group_result(
    items_by_id: dict[str, dict[str, Any]],
    score_key: str,
    group_items: list[dict[str, Any]],
    group_result: dict[str, Any],
) -> None:
    order_map = {item_id: idx for idx, item_id in enumerate(group_result["ordered_ids"], start=1)}
    reason_map = group_result.get("reason_map", {})
    group_summary = group_result.get("group_summary", "")
    group_size = len(group_items)
    for item in group_items:
        item_id = str(item.get("egp_id", ""))
        target = items_by_id[item_id]
        target["tie_group_score"] = item.get("llm_score")
        target["tie_group_size"] = group_size
        target["tie_group_order"] = order_map.get(item_id, group_size)
        target["tie_break_reason"] = reason_map.get(item_id, "")
        target["tie_break_group_summary"] = group_summary
        target["phase2_status"] = group_result["status"]


def finalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items.sort(
        key=lambda item: (
            float(item.get("llm_score", 100)),
            int(item.get("tie_group_order", 1) or 1),
            int(item.get("original_rank", 10**9) or 10**9),
            str(item.get("egp_id", "")),
        )
    )
    for final_rank, item in enumerate(items, start=1):
        item["phase2_rank"] = final_rank
    return items


def load_resume_document(path: Path, source_result_path: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = load_json(path)
    except Exception:  # noqa: BLE001
        return None
    metadata = data.get("metadata", {})
    if metadata.get("source_result_path") != source_result_path:
        return None
    return data


def build_output_document(
    cfg,
    source_doc: dict[str, Any],
    items: list[dict[str, Any]],
    llm: LLMClient | None,
    result_path: Path,
    run_started_at: str,
    llm_call_started_at: str | None,
    llm_call_finished_at: str | None,
    processed_group_scores: list[str],
    completed: bool,
    use_llm: bool,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).astimezone().isoformat()
    if llm is not None:
        llm_stats = llm.stats()
        call_count = llm_stats.get("call_count", 0) or 0
        input_tokens = llm_stats.get("total_input_tokens", 0) or 0
        output_tokens = llm_stats.get("total_output_tokens", 0) or 0
        sort_rule = "先按 step1 的 llm_score 从小到大排序；若分数相同，则按 phase2 的 tie_group_order 做组内螺旋学习排序"
    else:
        llm_stats = {"call_count": 0, "total_input_tokens": 0, "total_output_tokens": 0}
        call_count = input_tokens = output_tokens = 0
        sort_rule = "先按 step1 的 llm_score 从小到大排序；若分数相同，则按 EGP id 末尾数字升序（无LLM）"
    duplicate_groups = [group for group in group_same_scores(items) if len(group[1]) > 1]
    metadata: dict[str, Any] = {
        "generated_at": now,
        "run_started_at": run_started_at,
        "llm_call_started_at": llm_call_started_at,
        "llm_call_finished_at": llm_call_finished_at,
        "file_output_time": now,
        "run_completed_at": now if completed else None,
        "is_completed": completed,
        "level": cfg.level,
        "lang": cfg.lang,
        "model": cfg.llm.model if llm is not None else None,
        "openai_base_url": cfg.llm.base_url if llm is not None else None,
        "source_result_path": source_doc.get("metadata", {}).get("result_path") or "",
        "source_generated_at": source_doc.get("metadata", {}).get("generated_at"),
        "output_dir": str(cfg.output_dir),
        "result_path": str(result_path),
        "total_items": len(items),
        "duplicate_score_group_count": len(duplicate_groups),
        "processed_duplicate_score_groups": len(processed_group_scores),
        "processed_group_scores": processed_group_scores,
        "sort_rule": sort_rule,
        "use_llm": use_llm,
        "token_usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "avg_input_tokens_per_call": round(input_tokens / call_count, 2) if call_count else 0,
            "avg_output_tokens_per_call": round(output_tokens / call_count, 2) if call_count else 0,
        },
        "llm_stats": llm_stats,
    }
    if use_llm:
        metadata["phase2_prompt"] = {
            "fixed_prompt": cfg.phase1.fixed_prompt,
            "level_prompt": cfg.phase1.score_prompt,
            "response_schema": GROUP_RESPONSE_SCHEMA,
        }
    return {"metadata": metadata, "items": items}


def write_output(document: dict[str, Any], result_path: Path, latest_path: Path) -> None:
    write_json(result_path, document)
    write_json(latest_path, document)

def dry_run_phase2(cfg, source_doc, result_path: Path, latest_path: Path) -> list:
    """模拟Phase 2的同分排序过程"""
    logger.info("Dry run模式 - 模拟Phase 2同分排序过程")
    
    source_items = source_doc.get("items", [])
    if not source_items:
        logger.warning("源数据中没有items，无法进行排序")
        return []
    
    # 创建模拟分组排序结果
    working_items = build_working_items(source_items)
    
    # 模拟同分组的排序
    duplicate_groups = [group for group in group_same_scores(working_items) if len(group[1]) > 1]
    
    for score_key, group_items in duplicate_groups:
        logger.info(f"模拟排序同分组 {score_key} ({len(group_items)} items)")
        # 为每个同分组分配内在顺序
        for i, item in enumerate(group_items):
            item["tie_group_order"] = i + 1
            item["tie_reason"] = f"模拟分组排序，位置{i+1}"
    
    # 重新计算最终排名
    finalized_items = finalize_items(working_items)
    
    # 保存模拟结果
    document = build_output_document(
        cfg,
        source_doc,
        finalized_items,
        None,  # 无LLM客户端
        result_path=result_path,
        run_started_at=datetime.now(timezone.utc).astimezone().isoformat(),
        llm_call_started_at=None,
        llm_call_finished_at=None,
        processed_group_scores=[group[0] for group in duplicate_groups],
        completed=True,
        use_llm=False,
    )
    write_output(document, result_path, latest_path)
    
    return finalized_items


def main() -> None:
    args = parse_args()
    cfg = get_config(level=args.level, lang=args.lang)
    cfg.llm.model = args.model or "deepseek-reasoner"
    
    # 检查缓存
    cache_dir = Path("output") / args.level / "phase2"
    cache_file = cache_dir / "same_score_ordered.json"
    
    if not args.force_rerun and cache_file.exists():
        logger.info(f"使用缓存文件: {cache_file}")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            logger.info(f"✓ Phase 2 已完成 (使用缓存)，共{cached_data.get('total_items', 0)}条记录")
            return
        except Exception as e:
            logger.warning(f"缓存文件读取失败: {e}")

    use_llm = args.llm
    if use_llm and not cfg.llm.api_key and not args.dry_run:
        logger.error("OPENAI_API_KEY is not set")
        sys.exit(1)

    # 优先使用用户指定的输入文件，否则自动寻找Phase 1的输出文件
    if args.input:
        source_path = Path(args.input)
    else:
        # 检查多种可能的Phase 1输出文件路径
        possible_paths = [
            cfg.output_dir / "phase1" / "full_sort_latest.json",
            cfg.output_dir / "phase1" / "scored_items_latest.json"
        ]
        
        source_path = None
        for path in possible_paths:
            if path.exists():
                source_path = path
                logger.info(f"找到Phase 1输出文件: {path}")
                break
        
            if not source_path:
                # Dry run模式下创建模拟输入文件
                if args.dry_run:
                    logger.info("Dry run模式 - 创建模拟Phase 1输出文件")
                    phase1_dir = cfg.output_dir / "phase1"
                    phase1_dir.mkdir(parents=True, exist_ok=True)
                    source_path = phase1_dir / "scored_items.json"
                    
                    # 创建模拟Phase 1数据
                    mock_data = {
                        "metadata": {
                            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
                            "level": cfg.level,
                            "lang": cfg.lang,
                            "total_items": 109,
                            "sort_rule": "模拟排序规则"
                        },
                        "items": [
                            {
                                "egp_id": f"GG-{cfg.level}-{i:03d}",
                                "egp_info": {
                                    "guideword": f"语法点{i}",
                                    "can_do": f"能够做{i}",
                                    "category": "基础语法",
                                    "chinese_human_name": f"中文名称{i}",
                                    "examples": f"示例{i}"
                                },
                                "llm_score": 30 + i * 0.1,
                                "rank": i + 1,
                                "llm_reason": f"模拟评分理由{i}"
                            } for i in range(109)
                        ]
                    }
                    source_path.parent.mkdir(parents=True, exist_ok=True)
                    write_json(source_path, mock_data)
            else:
                logger.error("Phase 1结果文件未找到，请检查以下路径是否存在:")
                for path in possible_paths:
                    logger.error("  - %s", path)
                sys.exit(1)
    
    if not source_path.exists():
        logger.error("Step1 result not found: %s", source_path)
        sys.exit(1)

    source_doc = load_source_document(source_path)
    run_started_at = datetime.now(timezone.utc).astimezone().isoformat()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 创建phase2子目录
    phase2_dir = cfg.output_dir / "phase2"
    phase2_dir.mkdir(parents=True, exist_ok=True)
    
    result_path = phase2_dir / f"same_score_ordered_{timestamp}.json"
    latest_path = phase2_dir / "same_score_ordered_latest.json"
    
    # 确保缓存目录存在
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Dry run模式处理
    if args.dry_run:
        finalized_items = dry_run_phase2(cfg, source_doc, result_path, latest_path)
        logger.info("✓ Phase 2 Dry run完成，共处理%d条记录", len(finalized_items))
        logger.info("生成的文件:")
        logger.info("  - %s", result_path)
        logger.info("  - %s", latest_path)
        logger.info("Top 10同分排序结果:")
        for i, item in enumerate(finalized_items[:10], 1):
            logger.info("  #%d %s (原始排名: %d)", 
                       i, item.get("egp_id", ""), item.get("original_rank", 0))
        return

    source_items = source_doc.get("items", [])
    working_items = build_working_items(source_items)
    llm: LLMClient | None = LLMClient(cfg.llm) if use_llm else None
    processed_group_scores: list[str] = []
    first_llm_call_at: str | None = None
    last_llm_call_at: str | None = None

    if use_llm and args.resume:
        resume_doc = load_resume_document(latest_path, source_doc.get("metadata", {}).get("result_path") or "")
        if resume_doc is not None:
            logger.info("Resuming from %s", latest_path)
            working_items = resume_doc.get("items", working_items)
            processed_group_scores = list(resume_doc.get("metadata", {}).get("processed_group_scores", []))
            first_llm_call_at = resume_doc.get("metadata", {}).get("llm_call_started_at")
            last_llm_call_at = resume_doc.get("metadata", {}).get("llm_call_finished_at")

    items_by_id = {str(item.get("egp_id", "")): item for item in working_items}
    duplicate_groups = [group for group in group_same_scores(working_items) if len(group[1]) > 1]
    if args.limit_groups is not None:
        duplicate_groups = duplicate_groups[: args.limit_groups]

    logger.info("Loaded %s items from %s", len(working_items), source_path)
    logger.info(
        "Mode: %s; found %s duplicate-score groups to process",
        "LLM" if use_llm else "no-LLM (EGP id trailing number)",
        len(duplicate_groups),
    )

    for score_key, group_items in duplicate_groups:
        if use_llm and score_key in processed_group_scores:
            logger.info("Skipping duplicate-score group %s (already processed)", score_key)
            continue
        logger.info("Ordering same-score group %s (%s items)", score_key, len(group_items))
        if use_llm:
            group_result = resolve_group_order(
                llm,
                cfg,
                args.level,
                score_key,
                group_items,
                max_group_retries=args.max_group_retries,
                rate_limit_wait=args.rate_limit_wait,
                max_rate_limit_wait=args.max_rate_limit_wait,
            )
            if first_llm_call_at is None:
                first_llm_call_at = group_result.get("llm_call_started_at")
            if group_result.get("llm_call_finished_at"):
                last_llm_call_at = group_result.get("llm_call_finished_at")
        else:
            group_result = resolve_group_order_no_llm(group_items)
        apply_group_result(items_by_id, score_key, group_items, group_result)
        processed_group_scores.append(score_key)
        finalized_items = finalize_items(list(items_by_id.values()))
        document = build_output_document(
            cfg,
            source_doc,
            finalized_items,
            llm,
            result_path=result_path,
            run_started_at=run_started_at,
            llm_call_started_at=first_llm_call_at,
            llm_call_finished_at=last_llm_call_at,
            processed_group_scores=processed_group_scores,
            completed=False,
            use_llm=use_llm,
        )
        write_output(document, result_path, latest_path)
        if use_llm and args.sleep > 0:
            time.sleep(args.sleep)

    finalized_items = finalize_items(list(items_by_id.values()))
    document = build_output_document(
        cfg,
        source_doc,
        finalized_items,
        llm,
        result_path=result_path,
        run_started_at=run_started_at,
        llm_call_started_at=first_llm_call_at,
        llm_call_finished_at=last_llm_call_at,
        processed_group_scores=processed_group_scores,
        completed=True,
        use_llm=use_llm,
    )
    write_output(document, result_path, latest_path)

    logger.info("Saved result file: %s", result_path)
    logger.info("Updated latest file: %s", latest_path)
    logger.info("Top 10 phase2 order:")
    for item in finalized_items[:10]:
        logger.info(
            "  #%s score=%s group_order=%s %s",
            item["phase2_rank"],
            item.get("llm_score"),
            item.get("tie_group_order"),
            item.get("egp_id"),
        )


if __name__ == "__main__":
    main()
