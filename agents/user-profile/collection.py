"""P0 信息采集状态机：Baseline、25 题预算、放行判定。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from extract import CITY_COUNTRY, SKILL_SCORE_KEYS, coerce_skill_score, infer_geography
from field_clusters import VALID_CEFR, extract_cefr_from_text, normalize_field_value

MAX_QUESTIONS = 25

ROLE_ANCHORS = ("employed", "student", "freelancer", "career_change", "other")
LEVEL_BANDS = ("beginner", "elementary", "intermediate", "upper_intermediate", "advanced")
BOTTLENECKS = ("listening", "speaking", "reading", "writing", "general", "unknown")

# Baseline 锚点：B1–B4 必填；B5/B6 至少一项
BASELINE_CHECKS: list[dict[str, Any]] = [
    {"field": "growth.goal", "label": "学习目标"},
    {
        "field": "identity.role_anchor",
        "label": "身份角色",
        "alternates": ["identity.occupation"],
    },
    {"field": "identity.native_language", "label": "母语"},
    {
        "field": "identity.region_anchor",
        "label": "所在地区",
        "alternates": ["identity.country"],
    },
    {
        "field": "capability.level_band",
        "label": "整体英语水平",
        "alternates": ["capability.cefr"],
        "group": "level_or_bottleneck",
    },
    {
        "field": "capability.bottleneck_for_goal",
        "label": "目标瓶颈技能",
        "group": "level_or_bottleneck",
    },
]

BASELINE_QUESTIONS: dict[str, dict[str, str]] = {
    "growth.goal": {
        "question": "你希望通过英语学习达成什么目标？",
        "hint": "例：海外技术面试、远程协作、雅思 7 分、出国生活",
        "why": "一切路线都从你的目标出发，需要先对齐方向。",
        "depth": 1,
        "phase": "baseline",
    },
    "identity.role_anchor": {
        "question": "你现在的身份更接近哪一种？",
        "hint": "在职 / 学生 / 自由职业 / 转行中 / 其他",
        "why": "身份决定学习场景是职场、学业还是生活。",
        "depth": 1,
        "phase": "baseline",
    },
    "identity.occupation": {
        "question": "你目前的职业或专业方向是什么？",
        "hint": "例：前端工程师、大三计算机、全职妈妈",
        "why": "职业背景影响面试与沟通类内容的定制。",
        "depth": 1,
        "phase": "baseline",
    },
    "identity.native_language": {
        "question": "你的母语是什么？",
        "hint": "例：中文、日语",
        "why": "母语影响学习策略与常见干扰项。",
        "depth": 1,
        "phase": "baseline",
    },
    "identity.region_anchor": {
        "question": "你目前主要在哪个国家或地区？",
        "hint": "例：中国、新加坡、美国",
        "why": "地区影响考试体系、文化语境与内容本地化。",
        "depth": 1,
        "phase": "baseline",
    },
    "identity.country": {
        "question": "你目前主要在哪个国家或地区？",
        "hint": "例：中国、新加坡",
        "why": "地区影响考试体系与文化语境。",
        "depth": 1,
        "phase": "baseline",
    },
    "capability.level_band": {
        "question": "整体英语水平你自评在哪个档位？",
        "hint": "基础 / 初级 / 中级 / 中高级 / 高级（或 A1–C2）",
        "why": "需要粗粒度水平锚点，才能推荐合适难度的路线。",
        "depth": 1,
        "phase": "baseline",
    },
    "capability.cefr": {
        "question": "你自评当前的 CEFR 等级是？",
        "hint": "A1 / A2 / B1 / B2 / C1 / C2",
        "why": "水平档位帮助校准学习起点。",
        "depth": 1,
        "phase": "baseline",
    },
    "capability.bottleneck_for_goal": {
        "question": "为了实现你的目标，你觉得最拖后腿的是哪一项？",
        "hint": "听力 / 口语 / 阅读 / 写作 / 综合 / 不确定",
        "why": "瓶颈技能决定路线上的优先训练方向。",
        "depth": 3,
        "phase": "baseline",
    },
}


def empty_collection() -> dict[str, Any]:
    return {
        "question_count": 0,
        "budget_max": MAX_QUESTIONS,
        "budget_remaining": MAX_QUESTIONS,
        "asked_fields": [],
        "answered_effective": {},
        "confident_fields": {},
        "baseline_complete": False,
        "path": None,
        "path_confirmed": False,
        "assumptions": [],
        "unresolved_gaps": [],
        "batch_baseline_done": False,
        "mode": "batch_baseline",
        "release": {
            "status": "collecting",
            "confidence": 0.0,
        },
    }


def _get_path(obj: dict, path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _is_filled(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (int, float)):
        return True
    if isinstance(val, list):
        return len(val) > 0
    return bool(val)


def region_satisfied(twin: dict) -> bool:
    """地区/国家 baseline：有国家、region，或已知城市即可满足。"""
    ident = twin.get("identity") or {}
    if _is_filled(ident.get("region_anchor")) or _is_filled(ident.get("country")):
        return True
    city = (ident.get("city") or "").strip()
    return bool(city and city in CITY_COUNTRY)


def field_is_satisfied(twin: dict, field: str) -> bool:
    """判断某字段是否已有有效值（含语义簇等价）。"""
    from field_clusters import is_field_satisfied as cluster_aware_satisfied

    return cluster_aware_satisfied(twin, field)


def _field_satisfied(twin: dict, spec: dict[str, Any]) -> bool:
    field = spec["field"]
    if field in ("identity.region_anchor", "identity.country"):
        return region_satisfied(twin)
    if _is_filled(_get_path(twin, field)):
        return True
    for alt in spec.get("alternates") or []:
        if alt in ("identity.region_anchor", "identity.country"):
            if region_satisfied(twin):
                return True
        elif _is_filled(_get_path(twin, alt)):
            return True
    return False


def baseline_missing(twin: dict) -> list[str]:
    """返回尚未满足的 baseline 字段路径（主字段名）。"""
    missing: list[str] = []
    level_or_bottleneck_ok = False

    for spec in BASELINE_CHECKS:
        group = spec.get("group")
        if group == "level_or_bottleneck":
            if _field_satisfied(twin, spec):
                level_or_bottleneck_ok = True
            continue
        if not _field_satisfied(twin, spec):
            missing.append(spec["field"])

    if not level_or_bottleneck_ok:
        level_spec = {"field": "capability.level_band", "alternates": ["capability.cefr"]}
        if not _field_satisfied(twin, level_spec):
            missing.append("capability.level_band")
        else:
            missing.append("capability.bottleneck_for_goal")

    # 去重保序
    seen: set[str] = set()
    ordered: list[str] = []
    for f in missing:
        if f not in seen:
            seen.add(f)
            ordered.append(f)
    return ordered


def is_baseline_complete(twin: dict) -> bool:
    return len(baseline_missing(twin)) == 0


def set_twin_path(twin: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = twin
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def _normalize_role_anchor(raw: str) -> str:
    text = raw.strip().lower()
    mapping = {
        "在职": "employed",
        "工作": "employed",
        "employed": "employed",
        "学生": "student",
        "student": "student",
        "自由职业": "freelancer",
        "freelancer": "freelancer",
        "转行": "career_change",
        "career_change": "career_change",
    }
    for key, val in mapping.items():
        if key in text:
            return val
    return "other" if text else ""


def _normalize_level_band(raw: str) -> str:
    text = raw.strip().upper()
    cefr_map = {
        "A1": "beginner",
        "A2": "elementary",
        "B1": "intermediate",
        "B2": "upper_intermediate",
        "C1": "advanced",
        "C2": "advanced",
    }
    if text in cefr_map:
        return cefr_map[text]
    lower = raw.strip().lower()
    for band in LEVEL_BANDS:
        if band in lower or band.replace("_", "") in lower.replace(" ", ""):
            return band
    cn_map = {
        "基础": "beginner",
        "初级": "elementary",
        "中级": "intermediate",
        "中高级": "upper_intermediate",
        "高级": "advanced",
        "流利": "advanced",
    }
    for k, v in cn_map.items():
        if k in raw:
            return v
    return raw.strip()


def _normalize_bottleneck(raw: str) -> str:
    text = raw.strip().lower()
    for b in BOTTLENECKS:
        if b in text:
            return b
    cn = {
        "听力": "listening",
        "口语": "speaking",
        "阅读": "reading",
        "写作": "writing",
        "综合": "general",
        "不确定": "unknown",
    }
    for k, v in cn.items():
        if k in raw:
            return v
    return "unknown" if text else ""


def apply_answers(twin: dict, answers: dict[str, Any]) -> dict:
    skill_keys = {"listening", "speaking", "reading", "writing", "grammar", "vocabulary"}

    for path, raw in answers.items():
        if raw is None:
            continue
        if isinstance(raw, str) and not raw.strip():
            continue

        val: Any = raw.strip() if isinstance(raw, str) else raw
        section, key = path.split(".", 1) if "." in path else ("", path)

        if path == "identity.role_anchor":
            val = _normalize_role_anchor(str(val))
        elif path == "capability.level_band":
            extracted = extract_cefr_from_text(str(val))
            if extracted and extracted != "unknown":
                val = _normalize_level_band(extracted)
                twin["capability"]["level_band"] = val
                twin["capability"]["cefr"] = extracted
            else:
                val = _normalize_level_band(str(val))
                twin["capability"]["level_band"] = val
                if extracted == "unknown":
                    twin["capability"]["cefr"] = "unknown"
            if not twin["capability"].get("cefr") and str(raw).upper() in VALID_CEFR:
                twin["capability"]["cefr"] = str(raw).upper()
            continue
        elif path == "capability.bottleneck_for_goal":
            val = _normalize_bottleneck(str(val))
        elif path == "capability.cefr":
            extracted = extract_cefr_from_text(str(val))
            if extracted:
                val = extracted
            else:
                val = str(val).strip()
                if len(val) > 3 and val.upper() not in {"A1", "A2", "B1", "B2", "C1", "C2"}:
                    twin["capability"]["level_band"] = twin["capability"].get("level_band") or val
                    val = ""
            if val:
                twin["capability"]["cefr"] = val.upper() if val != "unknown" else "unknown"
                if not twin["capability"].get("level_band"):
                    twin["capability"]["level_band"] = _normalize_level_band(val)
            elif str(raw).strip():
                twin["capability"]["level_band"] = twin["capability"].get("level_band") or str(raw).strip()
            continue
        elif path in ("growth.timeline_urgency", "growth.deadline"):
            val = normalize_field_value(path, str(val))
        elif section == "capability" and key in skill_keys:
            coerced = coerce_skill_score(val)
            if coerced is not None:
                val = coerced
            else:
                continue

        if path in ("identity.region_anchor", "identity.country", "identity.city"):
            geo = infer_geography(str(val))
            if geo and geo.get("identity"):
                for key, gval in geo["identity"].items():
                    if gval and not _is_filled(twin["identity"].get(key)):
                        twin["identity"][key] = gval
                continue

        if path == "identity.region_anchor" and isinstance(val, str):
            set_twin_path(twin, path, val)
            if not _is_filled(twin["identity"].get("country")):
                twin["identity"]["country"] = val
            continue

        if path == "identity.country" and isinstance(val, str):
            set_twin_path(twin, path, val)
            if not _is_filled(twin["identity"].get("region_anchor")):
                twin["identity"]["region_anchor"] = val
            continue

        if path == "identity.occupation" and isinstance(val, str):
            set_twin_path(twin, path, val)
            if not _is_filled(twin["identity"].get("role_anchor")):
                twin["identity"]["role_anchor"] = "employed"
            continue

        set_twin_path(twin, path, val)

    return twin


def merge_collection(existing: dict | None, patch: dict | None) -> dict:
    base = empty_collection()
    if existing:
        base.update(deepcopy(existing))
    if patch:
        for key, val in patch.items():
            if key == "release" and isinstance(val, dict):
                base.setdefault("release", {}).update(val)
            else:
                base[key] = val
    base["budget_max"] = MAX_QUESTIONS
    base["budget_remaining"] = max(0, MAX_QUESTIONS - int(base.get("question_count") or 0))
    return base


def record_effective_answer(
    collection: dict,
    field: str | None,
    raw: str,
    inferred_fields: list[str] | None = None,
) -> dict:
    """记录有效回答（含语义簇等效）。"""
    if not field or not raw.strip():
        return collection
    ledger = dict(collection.get("answered_effective") or {})
    entry = {"raw": raw.strip(), "inferred": list(inferred_fields or [])}
    ledger[field] = entry
    from field_clusters import cluster_for_field, cluster_members

    cluster = cluster_for_field(field)
    if cluster:
        for member in cluster_members(cluster):
            if member not in ledger:
                ledger[member] = {**entry, "via_cluster": field}
    collection["answered_effective"] = ledger
    return collection


def record_question(collection: dict, field: str | None) -> dict:
    from field_clusters import record_cluster_ask

    collection = merge_collection(collection, None)
    collection["question_count"] = int(collection.get("question_count") or 0) + 1
    if field:
        asked = list(collection.get("asked_fields") or [])
        if field not in asked:
            asked.append(field)
        collection["asked_fields"] = asked
        collection = record_cluster_ask(collection, field)
    collection["budget_remaining"] = max(0, MAX_QUESTIONS - collection["question_count"])
    return collection


def baseline_question_for(field: str) -> dict[str, Any]:
    spec = BASELINE_QUESTIONS.get(field, {})
    return {
        "field": field,
        "question": spec.get("question", f"请补充：{field}"),
        "hint": spec.get("hint", ""),
        "why": spec.get("why", ""),
        "depth": spec.get("depth", 1),
        "phase": spec.get("phase", "baseline"),
        "skippable": False,
    }


def evaluate_release(
    twin: dict,
    collection: dict,
    *,
    path_blocking_gaps: list[str] | None = None,
    path_confidence: float = 0.0,
) -> dict[str, Any]:
    """判定放行状态，返回更新后的 release 对象。"""
    count = int(collection.get("question_count") or 0)
    baseline_ok = is_baseline_complete(twin)
    blocking = list(path_blocking_gaps or [])
    path_confirmed = bool(collection.get("path_confirmed"))
    confidence = float(path_confidence or 0.0)

    if count >= MAX_QUESTIONS:
        return {
            "status": "budget_exhausted",
            "confidence": confidence,
            "reason": f"已达 {MAX_QUESTIONS} 题上限，基于现有信息放行",
        }

    if not baseline_ok:
        return {
            "status": "blocked" if count >= MAX_QUESTIONS - 1 else "collecting",
            "confidence": confidence,
            "reason": "Baseline 锚点尚未齐备",
        }

    if not blocking and path_confirmed and confidence >= 0.75:
        return {
            "status": "early",
            "confidence": confidence,
            "reason": "路径已确认且关键信息充足",
        }

    if not blocking and confidence >= 0.6 and count >= 18:
        return {
            "status": "conditional",
            "confidence": confidence,
            "reason": "关键信息已齐，部分细节将用假设补全",
        }

    if not blocking and path_confirmed and confidence >= 0.65:
        return {
            "status": "conditional",
            "confidence": confidence,
            "reason": "路径可行，仍有可选信息未收集",
        }

    return {
        "status": "collecting",
        "confidence": confidence,
        "reason": "继续由浅入深收集",
    }


def phase_from_release(status: str) -> str:
    return {
        "early": "p0_sufficient",
        "conditional": "p0_conditional",
        "budget_exhausted": "p0_budget_exhausted",
        "blocked": "p0_collecting",
        "collecting": "p0_collecting",
    }.get(status, "p0_collecting")


def normalize_capability_scores(twin: dict) -> dict:
    """修正 twin 中可能为字符串的能力分数（如 LLM / JSON 回传）。"""
    cap = twin.get("capability")
    if not isinstance(cap, dict):
        return twin
    for key in SKILL_SCORE_KEYS:
        if key in cap:
            cap[key] = coerce_skill_score(cap.get(key))
    return twin


def score_label(score: int | str | float | None) -> str:
    n = coerce_skill_score(score)
    if n is None:
        return "未评估"
    if n < 60:
        return "不及格"
    if n < 75:
        return "及格"
    if n < 85:
        return "良好"
    return "优秀"


def completeness(twin: dict, collection: dict) -> dict[str, float]:
    baseline_total = 6
    baseline_done = baseline_total - len(baseline_missing(twin))
    path = collection.get("path") or {}
    required = path.get("required_fields") or []
    filled_required = sum(1 for f in required if _is_filled(_get_path(twin, f)))
    req_ratio = filled_required / len(required) if required else 1.0

    return {
        "baseline": round(baseline_done / baseline_total, 2),
        "path_fields": round(req_ratio, 2),
        "overall": round((baseline_done / baseline_total + req_ratio) / 2, 2),
    }


def build_handoff(twin: dict, collection: dict) -> dict[str, Any]:
    path = collection.get("path") or {}
    release = collection.get("release") or {}
    cap = twin.get("capability") or {}
    bottleneck = cap.get("bottleneck_for_goal") or "unknown"
    focus = [bottleneck] if bottleneck not in ("unknown", "general") else []

    return {
        "release_type": release.get("status", "collecting"),
        "path": path,
        "confidence": release.get("confidence", 0.0),
        "assumptions": collection.get("assumptions") or [],
        "unresolved_gaps": collection.get("unresolved_gaps") or [],
        "recommended_focus": focus,
    }
