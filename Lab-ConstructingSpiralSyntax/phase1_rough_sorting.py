# . 整体流程
# 第一次全量 LLM 调用
# 若无效：打日志 → 尝试 LLM 修正 → 若修正成功则使用
# 若仍无效：按现有重试次数（共 3 次）再次执行 1–2
# 若始终无效：回退到逐条 score_row 打分

from __future__ import annotations

import argparse
import csv
import importlib
import json
import logging
import re
import sys
import time
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
logger = logging.getLogger("score_main")

JSON_RESPONSE_SCHEMA = {
    "score": "0到100之间，越小表示越应更早进入当前CEFR等级学习路径",
    "reason": "置信度说明，10字以内",
}

FULL_SORT_JSON_RESPONSE_SCHEMA = [
    {
        "egp_id": "GG-XXX",
        "score": "0到100之间，越小表示越应更早进入当前CEFR等级学习路径",
        "reason": "可选，10字以内",
    }
]

FULL_SORT_INVALID_RETRIES = 2

FIX_INVALID_RESPONSE_PROMPT = """以下是一次全量排序任务的 LLM 原始输出，格式有误无法解析。

请将其修正为合法的 JSON 数组，每个元素必须包含 egp_id（字符串）和 score（0-100 的数字）。
- 只输出修正后的 JSON 数组，不要输出任何其它文字、解释或 markdown。
- 数组中的 egp_id 必须来自原始输出，不要凭空添加或删除条目。
- score 必须是单个数字，不能是区间或文本。

原始输出：
---
{raw_output}
---
请输出修正后的 JSON 数组："""

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_BLUE = "\033[34m"
ANSI_MAGENTA = "\033[35m"
ANSI_CYAN = "\033[36m"


def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def color_text(text: str, color: str, *, bold: bool = False) -> str:
    if not _supports_color():
        return text
    prefix = f"{ANSI_BOLD if bold else ''}{color}"
    return f"{prefix}{text}{ANSI_RESET}"


def log_color(level: str, text: str, color: str, *, bold: bool = False) -> None:
    message = color_text(text, color, bold=bold)
    getattr(logger, level)(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score and sort EGP items into a spiral learning order.",
    )
    parser.add_argument("--level", choices=list(CEFR_LEVELS), default="A1", help="CEFR level")
    parser.add_argument("--lang", default="en", help="Language code (default: en)")
    parser.add_argument(
        "--plugin",
        choices=("score", "full-sort"),
        default="full-sort",
        help="Plugin mode: per-row scoring or full dataset sort",
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry run模式，不实际调用API")
    parser.add_argument("--force-rerun", action="store_true", help="强制重新运行，忽略缓存")
    parser.add_argument(
        "--input",
        default=None,
        help="Optional input source. Supports CSV or JSON under output/",
    )
    parser.add_argument("--model", default=None, help="Override LLM model name (default: deepseek-reasoner)")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N rows")
    parser.add_argument("--sleep", type=float, default=2.0, help="Sleep seconds between LLM calls")
    parser.add_argument("--resume", action="store_true", help="Resume from output/latest.json if present")
    parser.add_argument(
        "--rate-limit-wait",
        type=float,
        default=20.0,
        help="Base wait seconds when hitting rate limit",
    )
    parser.add_argument(
        "--max-rate-limit-wait",
        type=float,
        default=180.0,
        help="Max wait seconds when rate limit keeps happening",
    )
    parser.add_argument(
        "--max-row-retries",
        type=int,
        default=12,
        help="Max retries per row before falling back",
    )
    return parser.parse_args()
    parser.add_argument("--limit", type=int, default=None, help="Only process first N rows")
    parser.add_argument("--sleep", type=float, default=2.0, help="Sleep seconds between LLM calls")
    parser.add_argument("--resume", action="store_true", help="Resume from output/latest.json if present")
    parser.add_argument(
        "--rate-limit-wait",
        type=float,
        default=20.0,
        help="Base wait seconds when hitting rate limit",
    )
    parser.add_argument(
        "--max-rate-limit-wait",
        type=float,
        default=180.0,
        help="Max wait seconds when rate limit keeps happening",
    )
    parser.add_argument(
        "--max-row-retries",
        type=int,
        default=12,
        help="Max retries per row before falling back",
    )
    return parser.parse_args()


def load_egp_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows: list[dict[str, str]] = []
        for row in reader:
            cleaned = {key: (value or "").strip() for key, value in row.items()}
            if cleaned.get("egp_id"):
                rows.append(cleaned)
        return rows


def load_rows_from_json_source(source_path: Path) -> list[dict[str, str]]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        raw_items = payload
    else:
        raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError(f"Unsupported JSON input format: {source_path}")

    rows: list[dict[str, str]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        row = item.get("egp_info", item)
        if not isinstance(row, dict):
            continue
        cleaned = {str(key): str(value or "").strip() for key, value in row.items()}
        if cleaned.get("egp_id"):
            rows.append(cleaned)
    return rows


def load_source_rows(cfg, input_path: str | None) -> tuple[list[dict[str, str]], Path]:
    if not input_path:
        return load_egp_rows(cfg.egp_csv_path), cfg.egp_csv_path

    source_path = Path(input_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Input source not found: {source_path}")
    if source_path.suffix.lower() == ".csv":
        return load_egp_rows(source_path), source_path
    if source_path.suffix.lower() == ".json":
        return load_rows_from_json_source(source_path), source_path
    raise ValueError(f"Unsupported input source: {source_path}")


def extract_guideword(content: str) -> str:
    if "CanDo:" in content:
        return content.split("CanDo:", 1)[0].strip().rstrip(".")
    return content.strip()


def extract_can_do(content: str) -> str:
    if "CanDo:" not in content:
        return ""
    return content.split("CanDo:", 1)[1].strip()


def build_prompt(level_prompt: str, fixed_prompt: str, row: dict[str, str]) -> str:
    item_payload = {
        # "egp_id": row.get("egp_id", ""),
        # "level": row.get("level", ""),
        # "guideword": extract_guideword(row.get("content", "")),
        "can_do": extract_can_do(row.get("content", "")),
        "category": row.get("category", ""),
        # "chinese_human_name": row.get("chinese_human_name", ""),
        "example": row.get("examples", "").split("、")[0] if row.get("examples", "") else "",
        # "trigger_lemmas": row.get("trigger_lemmas", ""),
        # "chinese_doc": row.get("chinese_doc", ""),
        # "core_rules": row.get("core_rules", ""),
        # "keywords": row.get("keywords", ""),
        # "common_errors": row.get("common_errors", ""),
    }
    return (
        # f"{fixed_prompt}\n\n"
        f"{level_prompt}\n\n"
        "请严格按照以下要求输出 JSON，不要输出任何额外文本：\n"
        f"{json.dumps(JSON_RESPONSE_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        "补充要求：\n"
        "1. score 必须是单个数字，不能返回区间、文本标签或解释，例如不能返回 21-25。\n"
        "2. 如果你判断该语法点大致落在某个区间，请输出该区间内最能代表该条目的一个具体分值。\n\n"
        "当前语法条目：\n"
        f"{json.dumps(item_payload, ensure_ascii=False, indent=2)}"
    )


def build_full_sort_prompt(level_prompt: str, fixed_prompt: str, rows: list[dict[str, str]]) -> str:
    items_payload = []
    for row in rows:
        items_payload.append(
            {
                "egp_id": row.get("egp_id", ""),
                "can_do": extract_can_do(row.get("content", "")),
                "category": row.get("category", ""),
                "example": row.get("examples", "").split("、")[0] if row.get("examples", "") else "",
            }
        )

    return (
        f"{level_prompt}\n\n"
        "现在不是逐条评分，而是做一次性全量排序。\n"
        "请基于同样的学习路径标准，直接对以下全部 EGP 条目进行整体排序与打分。\n"
        "你必须返回一个 JSON 数组，数组中的每个元素都至少包含 egp_id 和 score。\n"
        "请尽量覆盖全部输入条目；score 仍然是 0 到 100，越小表示越早学习。\n\n"
        "请严格按照以下要求输出 JSON，不要输出任何额外文本：\n"
        f"{json.dumps(FULL_SORT_JSON_RESPONSE_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        "补充要求：\n"
        "1. 必须返回 JSON 数组，而不是对象。\n"
        "2. 数组元素中的 egp_id 必须来自输入数据。\n"
        "3. score 必须是单个数字，不能返回区间、文本标签或解释。\n"
        "4. 同一语法范畴请尽量落在相近分数区间，减少模块穿插。\n\n"
        "当前全部语法条目：\n"
        f"{json.dumps(items_payload, ensure_ascii=False, indent=2)}"
    )


def normalize_score(value: Any) -> float:
    if isinstance(value, (int, float)):
        score = float(value)
    else:
        raw = str(value).strip()
        range_match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:-|~|to|—|–|至)\s*(-?\d+(?:\.\d+)?)", raw, flags=re.IGNORECASE)
        if range_match:
            start = float(range_match.group(1))
            end = float(range_match.group(2))
            score = (start + end) / 2
        else:
            number_match = re.search(r"-?\d+(?:\.\d+)?", raw)
            if not number_match:
                raise ValueError(f"Could not parse score from: {value!r}")
            score = float(number_match.group(0))
    if score < 0:
        return 0.0
    if score > 100:
        return 100.0
    return round(score, 4)


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "too many requests" in text or "rate limit" in text or "429" in text


def _try_regex_fix_json(text: str) -> str:
    """尝试用正则修复常见 JSON 格式问题。"""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"```\s*$", "", t, flags=re.MULTILINE)
    t = t.strip()
    # 修复尾部逗号: ,] 或 ,}
    t = re.sub(r",\s*]", "]", t)
    t = re.sub(r",\s*}", "}", t)
    # 修复单引号键名 (简化：不处理嵌套)
    return t


def _extract_json_value(text: str) -> Any:
    """从 LLM 返回文本中提取 JSON，正则修复失败则抛出。"""
    t = _try_regex_fix_json(text)

    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start_idx = t.find(start_char)
        end_idx = t.rfind(end_char)
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            slice_text = t[start_idx : end_idx + 1]
            try:
                return json.loads(slice_text)
            except json.JSONDecodeError as e:
                # 再试一次：去掉可能的多余尾部逗号
                fixed = re.sub(r",\s*\]", "]", slice_text)
                fixed = re.sub(r",\s*}", "}", fixed)
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    raise ValueError(f"JSON parse error at position {e.pos}: {e.msg}") from e

    raise ValueError("Could not extract JSON value from LLM response (no [ ] or { } found)")


def score_row(
    row: dict[str, str],
    llm: LLMClient,
    cfg,
    max_row_retries: int,
    rate_limit_wait: float,
    max_rate_limit_wait: float,
) -> dict[str, Any]:
    prompt = build_prompt(cfg.phase1.score_prompt, cfg.phase1.fixed_prompt, row)
    last_error: Exception | None = None
    first_attempt_started_at: str | None = None
    last_attempt_finished_at: str | None = None

    for attempt in range(max_row_retries):
        attempt_started_at = datetime.now(timezone.utc).astimezone().isoformat()
        if first_attempt_started_at is None:
            first_attempt_started_at = attempt_started_at
        try:
            response = llm.chat_json(prompt, cfg.phase1.fixed_prompt)
            last_attempt_finished_at = datetime.now(timezone.utc).astimezone().isoformat()
            score = normalize_score(
                response.get("score", response.get("llm_score", response.get("value")))
            )
            reason = str(
                response.get("reason", response.get("score_reason", response.get("rationale", "")))
            ).strip()
            if not reason:
                raise ValueError("LLM response missing reason")
            return {
                "status": "ok",
                "llm_score": score,
                "score_reason": reason,
                "llm_prompt": prompt,
                "llm_call_started_at": first_attempt_started_at,
                "llm_call_finished_at": last_attempt_finished_at,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            last_attempt_finished_at = datetime.now(timezone.utc).astimezone().isoformat()
            logger.warning("Score failed for %s (attempt %s): %s", row.get("egp_id"), attempt + 1, exc)
            if _is_rate_limit_error(exc) and attempt < max_row_retries - 1:
                wait_seconds = min(rate_limit_wait * (2 ** attempt), max_rate_limit_wait)
                logger.warning(
                    "Rate limit hit for %s, sleep %.1fs then retry",
                    row.get("egp_id"),
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue
            if attempt < max_row_retries - 1:
                time.sleep(cfg.llm.retry_delay)

    logger.error("Fallback score applied for %s: %s", row.get("egp_id"), last_error)
    return {
        "status": "error",
        "llm_score": 100.0,
        "score_reason": f"LLM 评分失败，已回退到末尾排序。错误：{last_error}",
        "llm_prompt": prompt,
        "llm_call_started_at": first_attempt_started_at,
        "llm_call_finished_at": last_attempt_finished_at,
    }


def sort_items_in_place(items: list[dict[str, Any]]) -> None:
    items.sort(
        key=lambda item: (
            item["llm_score"],
            item.get("full_sort_return_index", 10**9),
            item["egp_id"],
        )
    )
    for rank, item in enumerate(items, start=1):
        item["rank"] = rank


def build_result_item(
    row: dict[str, str],
    scored: dict[str, Any],
    *,
    status: str,
    return_index: int | None = None,
) -> dict[str, Any]:
    result = {
        "egp_id": row.get("egp_id", ""),
        "llm_score": scored["llm_score"],
        "score_reason": scored.get("score_reason", ""),
        "status": status,
        "egp_info": {
            **row,
            "guideword": extract_guideword(row.get("content", "")),
            "can_do": extract_can_do(row.get("content", "")),
        },
        "llm_prompt": scored.get("llm_prompt"),
    }
    if return_index is not None:
        result["full_sort_return_index"] = return_index
    return result


def load_resume_items(latest_path: Path) -> list[dict[str, Any]]:
    if not latest_path.exists():
        return []
    try:
        payload = json.loads(latest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Skip invalid latest.json: %s", latest_path)
        return []
    items = payload.get("items", [])
    return items if isinstance(items, list) else []


def build_output_items(
    rows: list[dict[str, str]],
    llm: LLMClient,
    cfg,
    sleep_seconds: float,
    latest_path: Path,
    result_path: Path,
    run_started_at: str,
    resume: bool,
    max_row_retries: int,
    rate_limit_wait: float,
    max_rate_limit_wait: float,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    results = load_resume_items(latest_path) if resume else []
    existing_by_id = {item.get("egp_id"): item for item in results}
    total = len(rows)
    first_llm_call_at: str | None = None
    last_llm_call_at: str | None = None

    for index, row in enumerate(rows, start=1):
        egp_id = row.get("egp_id")
        if egp_id in existing_by_id:
            logger.info("Skipping %s/%s: %s (already processed)", index, total, egp_id)
            continue

        logger.info("Scoring %s/%s: %s", index, total, egp_id)
        scored = score_row(
            row,
            llm,
            cfg,
            max_row_retries=max_row_retries,
            rate_limit_wait=rate_limit_wait,
            max_rate_limit_wait=max_rate_limit_wait,
        )
        if first_llm_call_at is None:
            first_llm_call_at = scored.get("llm_call_started_at")
        if scored.get("llm_call_finished_at"):
            last_llm_call_at = scored.get("llm_call_finished_at")
        result = {
            **build_result_item(row, scored, status=scored["status"]),
        }
        results.append(result)
        existing_by_id[result["egp_id"]] = result
        sort_items_in_place(results)
        document = build_output_document(
            cfg,
            results,
            llm,
            run_started_at=run_started_at,
            result_path=result_path,
            first_llm_call_at=first_llm_call_at,
            last_llm_call_at=last_llm_call_at,
            completed=False,
        )
        write_output(document, result_path, latest_path)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    sort_items_in_place(results)
    return results, first_llm_call_at, last_llm_call_at


def normalize_full_sort_entries(
    raw_value: Any,
    rows_by_id: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if isinstance(raw_value, dict):
        for key in ("items", "results", "data", "ordered_items"):
            candidate = raw_value.get(key)
            if isinstance(candidate, list):
                raw_value = candidate
                break
    if not isinstance(raw_value, list):
        raise ValueError("Full-sort response is not a JSON array")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_ids: list[str] = []
    unknown_ids: list[str] = []
    invalid_score_ids: list[str] = []

    for entry in raw_value:
        if not isinstance(entry, dict):
            continue
        egp_id = str(entry.get("egp_id", "")).strip()
        if not egp_id:
            continue
        if egp_id not in rows_by_id:
            unknown_ids.append(egp_id)
            continue
        if egp_id in seen:
            duplicate_ids.append(egp_id)
            continue
        try:
            score = normalize_score(entry.get("score", entry.get("llm_score", entry.get("value"))))
        except Exception:  # noqa: BLE001
            invalid_score_ids.append(egp_id)
            continue
        seen.add(egp_id)
        normalized.append(
            {
                "egp_id": egp_id,
                "llm_score": score,
                "score_reason": str(entry.get("reason", entry.get("score_reason", ""))).strip(),
            }
        )

    return normalized, {
        "returned_count": len(raw_value),
        "valid_unique_count": len(normalized),
        "duplicate_ids": duplicate_ids,
        "unknown_ids": unknown_ids,
        "invalid_score_ids": invalid_score_ids,
    }


def build_full_sort_output_document(
    cfg,
    items: list[dict[str, Any]],
    llm: LLMClient,
    *,
    run_started_at: str,
    result_path: Path,
    source_path: Path,
    first_llm_call_at: str | None,
    last_llm_call_at: str | None,
    full_sort_prompt: str,
    full_sort_validation: dict[str, Any],
    missing_inserted_ids: list[str],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).astimezone()
    llm_stats = llm.stats()
    call_count = llm_stats.get("call_count", 0) or 0
    input_tokens = llm_stats.get("total_input_tokens", 0) or 0
    output_tokens = llm_stats.get("total_output_tokens", 0) or 0
    return {
        "metadata": {
            "generated_at": now.isoformat(),
            "run_started_at": run_started_at,
            "llm_call_started_at": first_llm_call_at,
            "llm_call_finished_at": last_llm_call_at,
            "file_output_time": now.isoformat(),
            "run_completed_at": now.isoformat(),
            "is_completed": True,
            "level": cfg.level,
            "lang": cfg.lang,
            "plugin": "full-sort",
            "model": cfg.llm.model,
            "openai_base_url": cfg.llm.base_url,
            "llm_max_tokens": cfg.llm.max_tokens,
            "llm_context_window": cfg.llm.context_window,
            "source_path": str(source_path),
            "csv_path": str(cfg.egp_csv_path),
            "output_dir": str(cfg.output_dir),
            "result_path": str(result_path),
            "total_items": len(items),
            "success_count": sum(1 for item in items if str(item.get("status", "")).startswith("ok")),
            "error_count": sum(1 for item in items if not str(item.get("status", "")).startswith("ok")),
            "sort_rule": "优先采用全量 LLM 返回的分数；缺失/非法项使用原有逐条打分并插入到全量排序结果中",
            "prompt": {
                "fixed_prompt": cfg.phase1.fixed_prompt,
                "level_prompt": cfg.phase1.score_prompt,
                "response_schema": FULL_SORT_JSON_RESPONSE_SCHEMA,
                "full_sort_prompt": full_sort_prompt,
                "fallback_response_schema": JSON_RESPONSE_SCHEMA,
            },
            "full_sort_validation": {
                **full_sort_validation,
                "missing_inserted_count": len(missing_inserted_ids),
                "missing_inserted_ids": missing_inserted_ids,
            },
            "token_usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "avg_input_tokens_per_call": round(input_tokens / call_count, 2) if call_count else 0,
                "avg_output_tokens_per_call": round(output_tokens / call_count, 2) if call_count else 0,
            },
            "llm_stats": llm_stats,
        },
        "items": items,
    }


def run_full_sort(
    rows: list[dict[str, str]],
    llm: LLMClient,
    cfg,
    source_path: Path,
    *,
    result_path: Path,
    latest_path: Path,
    run_started_at: str,
    sleep_seconds: float,
    max_row_retries: int,
    rate_limit_wait: float,
    max_rate_limit_wait: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], str | None, str | None]:
    rows_by_id = {row["egp_id"]: row for row in rows if row.get("egp_id")}
    prompt = build_full_sort_prompt(cfg.phase1.score_prompt, cfg.phase1.fixed_prompt, rows)
    first_llm_call_at = datetime.now(timezone.utc).astimezone().isoformat()
    last_llm_call_at: str | None = None

    normalized_entries: list[dict[str, Any]] = []
    validation: dict[str, Any] = {
        "returned_count": 0,
        "valid_unique_count": 0,
        "duplicate_ids": [],
        "unknown_ids": [],
        "invalid_score_ids": [],
        "full_sort_attempts": 0,
        "attempt_logs": [],
    }
    last_full_sort_error: str | None = None
    max_attempts = 1 + FULL_SORT_INVALID_RETRIES

    for attempt in range(1, max_attempts + 1):
        log_color(
            "info",
            f"[Full-sort] 开始第 {attempt}/{max_attempts} 次全量排序请求",
            ANSI_CYAN,
            bold=True,
        )
        validation["full_sort_attempts"] = attempt
        raw_response: str | None = None
        attempt_log: dict[str, Any] = {"attempt": attempt}
        try:
            raw_response = llm.chat(prompt, cfg.phase1.fixed_prompt)
            last_llm_call_at = datetime.now(timezone.utc).astimezone().isoformat()
            attempt_log["raw_response_preview"] = raw_response[: cfg.llm.response_preview_chars]
            raw_value = _extract_json_value(raw_response)
            normalized_entries, validation_result = normalize_full_sort_entries(raw_value, rows_by_id)
            validation.update(validation_result)
            if normalized_entries:
                remaining_count = len(rows_by_id) - len(normalized_entries)
                attempt_log["status"] = "success"
                attempt_log["valid_unique_count"] = len(normalized_entries)
                validation["attempt_logs"].append(attempt_log)
                log_color(
                    "info",
                    (
                        f"[Full-sort] 原始全量返回可用: {len(normalized_entries)} 条，"
                        f"剩余待旧版逐条回填: {remaining_count} 条"
                    ),
                    ANSI_GREEN,
                    bold=True,
                )
                break
            last_full_sort_error = "Full-sort response contains no valid unique items"
            attempt_log["status"] = "invalid_empty"
            attempt_log["error"] = last_full_sort_error
            log_color(
                "warning",
                f"[Full-sort] 第 {attempt}/{max_attempts} 次返回无有效条目: {last_full_sort_error}",
                ANSI_YELLOW,
                bold=True,
            )
        except Exception as exc:  # noqa: BLE001
            last_full_sort_error = str(exc)
            attempt_log["status"] = "parse_error"
            attempt_log["error"] = str(exc)
            if raw_response:
                attempt_log["raw_response_preview"] = raw_response[: cfg.llm.response_preview_chars]
            log_color(
                "warning",
                f"[Full-sort] 第 {attempt}/{max_attempts} 次解析失败: {exc}",
                ANSI_YELLOW,
                bold=True,
            )

        if not normalized_entries and raw_response:
            logger.info(
                "Full-sort raw response (first %d chars): %s",
                min(cfg.llm.response_preview_chars, len(raw_response)),
                (
                    raw_response[: cfg.llm.response_preview_chars] + "..."
                    if len(raw_response) > cfg.llm.response_preview_chars
                    else raw_response
                ),
            )
            fix_prompt = FIX_INVALID_RESPONSE_PROMPT.format(
                raw_output=raw_response[: cfg.llm.invalid_fix_input_chars]
            )
            log_color(
                "info",
                f"[Full-sort] 尝试使用 AI 修正返回格式，第 {attempt}/{max_attempts} 次",
                ANSI_BLUE,
                bold=True,
            )
            try:
                fix_response = llm.chat(fix_prompt, "你仅输出修正后的合法 JSON 数组，不输出任何其它内容。")
                last_llm_call_at = datetime.now(timezone.utc).astimezone().isoformat()
                attempt_log["fix_response_preview"] = fix_response[: cfg.llm.response_preview_chars]
                fix_value = _extract_json_value(fix_response)
                normalized_entries, validation_result = normalize_full_sort_entries(fix_value, rows_by_id)
                validation.update(validation_result)
                validation["fixed_by_llm"] = True
                if normalized_entries:
                    remaining_count = len(rows_by_id) - len(normalized_entries)
                    attempt_log["status"] = "fixed_by_llm"
                    attempt_log["valid_unique_count"] = len(normalized_entries)
                    validation["attempt_logs"].append(attempt_log)
                    log_color(
                        "info",
                        (
                            f"[Full-sort] AI 修正成功: 修正后可用 {len(normalized_entries)} 条，"
                            f"剩余待旧版逐条回填 {remaining_count} 条"
                        ),
                        ANSI_GREEN,
                        bold=True,
                    )
                    break
                attempt_log["fix_error"] = "LLM fix response still contains no valid unique items"
                log_color(
                    "warning",
                    "[Full-sort] AI 修正后仍无有效条目",
                    ANSI_YELLOW,
                    bold=True,
                )
            except Exception as fix_exc:  # noqa: BLE001
                attempt_log["fix_error"] = str(fix_exc)
                log_color(
                    "warning",
                    f"[Full-sort] AI 修正失败: {fix_exc}",
                    ANSI_YELLOW,
                    bold=True,
                )
                last_full_sort_error = f"{last_full_sort_error}; fix failed: {fix_exc}"

        validation["attempt_logs"].append(attempt_log)
        if attempt < max_attempts:
            time.sleep(cfg.llm.retry_delay)

    if not normalized_entries:
        log_color(
            "warning",
            (
                f"[Full-sort] 连续 {max_attempts} 次全量排序都无效，"
                "将对全部条目回退到旧版逐条打分"
            ),
            ANSI_RED,
            bold=True,
        )
        validation["full_sort_error"] = last_full_sort_error or "Unknown full-sort error"

    items: list[dict[str, Any]] = []
    returned_ids: set[str] = set()
    for idx, entry in enumerate(normalized_entries, start=1):
        row = rows_by_id[entry["egp_id"]]
        items.append(
            build_result_item(
                row,
                {
                    "llm_score": entry["llm_score"],
                    "score_reason": entry.get("score_reason", ""),
                    "llm_prompt": "full-sort 手动删除prompt",
                },
                status="ok_full_sort",
                return_index=idx,
            )
        )
        returned_ids.add(entry["egp_id"])

    missing_inserted_ids: list[str] = []
    fallback_success_count = 0
    fallback_error_count = 0
    for row in rows:
        egp_id = row.get("egp_id", "")
        if egp_id in returned_ids:
            continue
        logger.info("Full-sort missing/invalid id, fallback scoring: %s", egp_id)
        scored = score_row(
            row,
            llm,
            cfg,
            max_row_retries=max_row_retries,
            rate_limit_wait=rate_limit_wait,
            max_rate_limit_wait=max_rate_limit_wait,
        )
        if scored.get("llm_call_finished_at"):
            last_llm_call_at = scored["llm_call_finished_at"]
        fallback_status = "ok_fallback" if scored["status"] == "ok" else "error_fallback"
        items.append(build_result_item(row, scored, status=fallback_status))
        missing_inserted_ids.append(egp_id)
        if fallback_status == "ok_fallback":
            fallback_success_count += 1
        else:
            fallback_error_count += 1
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    validation["full_sort_success_count"] = len(returned_ids)
    validation["full_sort_missing_count"] = len(missing_inserted_ids)
    validation["fallback_success_count"] = fallback_success_count
    validation["fallback_error_count"] = fallback_error_count

    if validation.get("full_sort_error") or missing_inserted_ids:
        log_color(
            "warning",
            (
                "[Full-sort] 汇总: "
                f"全量成功 {validation['full_sort_success_count']} 条, "
                f"待旧版回填 {validation['full_sort_missing_count']} 条, "
                f"回填成功 {validation['fallback_success_count']} 条, "
                f"回填失败 {validation['fallback_error_count']} 条"
            ),
            ANSI_MAGENTA,
            bold=True,
        )
    else:
        log_color(
            "info",
            (
                f"[Full-sort] 全量排序完全成功，共 {validation['full_sort_success_count']} 条，"
                "无需旧版回填"
            ),
            ANSI_GREEN,
            bold=True,
        )

    sort_items_in_place(items)
    document = build_full_sort_output_document(
        cfg,
        items,
        llm,
        run_started_at=run_started_at,
        result_path=result_path,
        source_path=source_path,
        first_llm_call_at=first_llm_call_at,
        last_llm_call_at=last_llm_call_at,
        full_sort_prompt=prompt,
        full_sort_validation=validation,
        missing_inserted_ids=missing_inserted_ids,
    )
    write_output(document, result_path, latest_path)
    if validation.get("full_sort_error") or missing_inserted_ids or fallback_error_count > 0:
        failed_path = cfg.output_dir / "失败.json"
        failed_document = json.loads(json.dumps(document, ensure_ascii=False))
        failed_document["metadata"]["result_path"] = str(failed_path)
        failed_document["metadata"]["is_failed_output"] = True
        failed_path.write_text(json.dumps(failed_document, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.warning("Wrote failed full-sort result to %s", failed_path)
    return items, validation, first_llm_call_at, last_llm_call_at


def build_output_document(
    cfg,
    items: list[dict[str, Any]],
    llm: LLMClient,
    run_started_at: str,
    result_path: Path,
    first_llm_call_at: str | None = None,
    last_llm_call_at: str | None = None,
    completed: bool = False,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).astimezone()
    llm_stats = llm.stats()
    call_count = llm_stats.get("call_count", 0) or 0
    input_tokens = llm_stats.get("total_input_tokens", 0) or 0
    output_tokens = llm_stats.get("total_output_tokens", 0) or 0
    return {
        "metadata": {
            "generated_at": now.isoformat(),
            "run_started_at": run_started_at,
            "llm_call_started_at": first_llm_call_at,
            "llm_call_finished_at": last_llm_call_at,
            "file_output_time": now.isoformat(),
            "run_completed_at": now.isoformat() if completed else None,
            "is_completed": completed,
            "level": cfg.level,
            "lang": cfg.lang,
            "model": cfg.llm.model,
            "openai_base_url": cfg.llm.base_url,
            "llm_max_tokens": cfg.llm.max_tokens,
            "llm_context_window": cfg.llm.context_window,
            "csv_path": str(cfg.egp_csv_path),
            "output_dir": str(cfg.output_dir),
            "result_path": str(result_path),
            "total_items": len(items),
            "success_count": sum(1 for item in items if item["status"] == "ok"),
            "error_count": sum(1 for item in items if item["status"] != "ok"),
            "sort_rule": "按 llm_score 从小到大排序；分数越小表示越应更早进入该等级的螺旋学习路径",
            "prompt": {
                "fixed_prompt": cfg.phase1.fixed_prompt,
                "level_prompt": cfg.phase1.score_prompt,
                "response_schema": JSON_RESPONSE_SCHEMA,
            },
            "token_usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "avg_input_tokens_per_call": round(input_tokens / call_count, 2) if call_count else 0,
                "avg_output_tokens_per_call": round(output_tokens / call_count, 2) if call_count else 0,
            },
            "llm_stats": llm_stats,
        },
        "items": items,
    }


def write_output(document: dict[str, Any], result_path: Path, latest_path: Path) -> tuple[Path, Path]:
    payload = json.dumps(document, ensure_ascii=False, indent=2)
    result_path.write_text(payload, encoding="utf-8")
    latest_path.write_text(payload, encoding="utf-8")
    return result_path, latest_path


def dry_run_scoring(cfg, rows, result_path: Path, latest_path: Path) -> list:
    """模拟Phase 1的评分过程"""
    logger.info("Dry run模式 - 模拟Phase 1评分过程")
    
    # 创建模拟评分结果
    items = []
    for i, row in enumerate(rows):
        # 基于难度和位置模拟评分
        difficulty_factor = i % 3 + 1  # 1-3的难度等级
        position_factor = (i % 10) * 0.5  # 位置影响
        score = 20 + (difficulty_factor * 15) + position_factor  # 20-65分范围
        
        item = {
            "egp_id": row.get("egp_id", f"GG-{i+1:03d}"),
            "llm_score": float(score),
            "rank": i + 1,
            "status": "ok",
            "reason": f"难度{difficulty_factor}，位置{i+1}",
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat()
        }
        items.append(item)
    
    # 按分数排序(分数越低越早学习)
    items.sort(key=lambda x: x["llm_score"])
    for i, item in enumerate(items):
        item["rank"] = i + 1
    
    # 保存模拟结果
    document = {
        "metadata": {
            "level": cfg.level,
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "mode": "dry_run",
            "total_items": len(items),
            "success_count": len(items),
            "error_count": 0
        },
        "items": items
    }
    
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(document, f, ensure_ascii=False, indent=2)
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(document, f, ensure_ascii=False, indent=2)
    
    return items


def main() -> None:
    args = parse_args()
    cfg = get_config(level=args.level, lang=args.lang)
    if args.model:
        cfg.llm.model = args.model
    else:
        cfg.llm.model = "deepseek-reasoner"
    
    cfg.output_dir = cfg.output_dir / "phase1"
    cfg.output_dir.mkdir(parents=True, exist_ok=True)



    # 检查缓存
    cache_dir = Path("output") / args.level / "phase1"
    cache_file = cache_dir / "scored_items.json"
    
    if not args.force_rerun and cache_file.exists():
        logger.info(f"使用缓存文件: {cache_file}")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            logger.info(f"✓ Phase 1 已完成 (使用缓存)，共{cached_data.get('total_items', 0)}条记录")
            return
        except Exception as e:
            logger.warning(f"缓存文件读取失败: {e}")

    if not cfg.phase1.score_prompt:
        logger.error("Missing level prompt config for %s", cfg.level)
        sys.exit(1)

    try:
        rows, source_path = load_source_rows(cfg, args.input)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load input rows: %s", exc)
        sys.exit(1)
    if args.limit is not None:
        rows = rows[: args.limit]
    logger.info("Loaded %s rows from %s", len(rows), source_path)

    # Dry run模式处理
    if args.dry_run:
        logger.info("Phase 1 Dry run模式启动")
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建结果路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_path = cache_dir / f"scored_items_{timestamp}.json"
        latest_path = cache_dir / "scored_items.json"
        
        items = dry_run_scoring(cfg, rows, result_path, latest_path)
        
        logger.info("✓ Phase 1 Dry run完成，共处理%d条记录", len(items))
        logger.info("生成的文件:")
        logger.info("  - %s", result_path)
        logger.info("  - %s", latest_path)
        logger.info("Top 10学习路径顺序:")
        for item in items[:10]:
            logger.info("  #%s %.1f %s", item["rank"], item["llm_score"], item["egp_id"])
        return

    llm = LLMClient(cfg.llm)
    run_started_at = datetime.now(timezone.utc).astimezone().isoformat()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 确保缓存目录存在
    cache_dir.mkdir(parents=True, exist_ok=True)
    if args.plugin == "full-sort":
        result_path = cfg.output_dir / f"full_sort_{timestamp}.json"
        latest_path = cfg.output_dir / "full_sort_latest.json"
        items, validation, _, _ = run_full_sort(
            rows,
            llm,
            cfg,
            source_path,
            result_path=result_path,
            latest_path=latest_path,
            run_started_at=run_started_at,
            sleep_seconds=args.sleep,
            max_row_retries=args.max_row_retries,
            rate_limit_wait=args.rate_limit_wait,
            max_rate_limit_wait=args.max_rate_limit_wait,
        )
        logger.info(
            "Full-sort validation: valid=%s duplicate=%s unknown=%s invalid_score=%s missing_inserted=%s",
            validation.get("valid_unique_count", 0),
            len(validation.get("duplicate_ids", [])),
            len(validation.get("unknown_ids", [])),
            len(validation.get("invalid_score_ids", [])),
            sum(1 for item in items if item.get("status") in {"ok_fallback", "error_fallback"}),
        )
        log_color(
            "info",
            (
                f"[Full-sort] 终态: valid={validation.get('valid_unique_count', 0)}, "
                f"duplicate={len(validation.get('duplicate_ids', []))}, "
                f"unknown={len(validation.get('unknown_ids', []))}, "
                f"invalid_score={len(validation.get('invalid_score_ids', []))}, "
                f"fallback={sum(1 for item in items if item.get('status') in {'ok_fallback', 'error_fallback'})}"
            ),
            ANSI_CYAN,
            bold=True,
        )
    else:
        result_path = cfg.output_dir / f"{cfg.phase1.output_filename_prefix}_{timestamp}.json"
        latest_path = cfg.output_dir / "latest.json"
        items, first_llm_call_at, last_llm_call_at = build_output_items(
            rows,
            llm,
            cfg,
            args.sleep,
            latest_path=latest_path,
            result_path=result_path,
            run_started_at=run_started_at,
            resume=args.resume,
            max_row_retries=args.max_row_retries,
            rate_limit_wait=args.rate_limit_wait,
            max_rate_limit_wait=args.max_rate_limit_wait,
        )
        document = build_output_document(
            cfg,
            items,
            llm,
            run_started_at=run_started_at,
            result_path=result_path,
            first_llm_call_at=first_llm_call_at,
            last_llm_call_at=last_llm_call_at,
            completed=True,
        )
        result_path, latest_path = write_output(document, result_path, latest_path)

    logger.info("Saved result file: %s", result_path)
    logger.info("Updated latest file: %s", latest_path)
    logger.info("Top 10 learning path order:")
    for item in items[:10]:
        logger.info("  #%s %.4f %s", item["rank"], item["llm_score"], item["egp_id"])


if __name__ == "__main__":
    main()
