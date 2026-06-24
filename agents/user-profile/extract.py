"""从个人故事提取 P0 字段：优先 LLM（agents/_lib），失败则启发式。"""

from __future__ import annotations

import re
from typing import Any

SKILL_SCORE_KEYS = frozenset(
    {"listening", "speaking", "reading", "writing", "grammar", "vocabulary"}
)


def coerce_skill_score(val: Any) -> int | None:
    """将能力分数字段规范为 0–100 整数；无法解析则返回 None。"""
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return max(0, min(100, int(val)))
    if isinstance(val, str):
        text = val.strip()
        if not text:
            return None
        try:
            return max(0, min(100, int(float(text))))
        except ValueError:
            return None
    return None

# P0 身份字段优先级
IDENTITY_FIELDS = [
    "occupation",
    "country",
    "native_language",
    "city",
    "age_range",
    "name",
    "industry",
    "education_level",
]

COUNTRY_HINTS = {
    "中国": "中国",
    "china": "中国",
    "美国": "美国",
    "usa": "美国",
    "日本": "日本",
    "新加坡": "新加坡",
}

LANG_HINTS = {
    "中文": "中文",
    "汉语": "中文",
    "母语中文": "中文",
    "英语": "英语",
    "english": "英语",
}

OCCUPATION_HINTS = [
    (r"前端", "前端工程师"),
    (r"后端", "后端工程师"),
    (r"全栈", "全栈工程师"),
    (r"程序员|工程师|开发", "软件工程师"),
    (r"产品", "产品经理"),
    (r"设计", "设计师"),
    (r"学生", "学生"),
    (r"老师|教师", "教师"),
]

GOAL_HINTS = [
    (r"海外.{0,6}工作|出国工作", "海外工作"),
    (r"海外.{0,6}面试|技术面试", "海外技术面试"),
    (r"远程", "远程协作"),
    (r"雅思|托福|IELTS|TOEFL", "留学/考试"),
]

CITY_COUNTRY = {
    "上海": "中国",
    "北京": "中国",
    "深圳": "中国",
    "广州": "中国",
    "杭州": "中国",
    "成都": "中国",
    "南京": "中国",
    "武汉": "中国",
    "西安": "中国",
    "重庆": "中国",
    "天津": "中国",
    "苏州": "中国",
    "厦门": "中国",
    "青岛": "中国",
    "大连": "中国",
    "香港": "中国",
    "台北": "中国",
}

NAME_PATTERN = re.compile(r"我叫([\u4e00-\u9fa5A-Za-z]{1,12})")
CEFR_PATTERN = re.compile(r"\b(A1|A2|B1|B2|C1|C2)\b", re.I)
AGE_PATTERN = re.compile(r"(\d{1,2})\s*岁")
EDUCATION_HINTS = [
    (r"博士", "博士"),
    (r"硕士|研究生", "硕士"),
    (r"本科|学士|大学", "本科"),
    (r"大专|专科", "大专"),
    (r"高中", "高中"),
]
MARITAL_HINTS = [
    (r"未婚", "未婚"),
    (r"已婚", "已婚"),
    (r"离异|离婚", "离异"),
    (r"单身", "未婚"),
]
SCORE_PATTERN = re.compile(r"(听力|口语|阅读|写作|语法|词汇)[^\d]{0,6}(\d{1,3})", re.I)
TIMELINE_PATTERN = re.compile(r"(\d+)\s*个?\s*月")
TARGET_MARKET_HINTS = [
    (r"硅谷|美国|北美", "美国"),
    (r"欧洲|英国|德国", "欧洲"),
    (r"东南亚|新加坡", "东南亚"),
    (r"加拿大", "加拿大"),
    (r"澳洲|澳大利亚", "澳大利亚"),
]

SKILL_KEY_MAP = {
    "听力": "listening",
    "口语": "speaking",
    "阅读": "reading",
    "写作": "writing",
    "语法": "grammar",
    "词汇": "vocabulary",
}


def _empty_identity() -> dict[str, str]:
    return {
        "name": "",
        "age_range": "",
        "country": "",
        "region_anchor": "",
        "city": "",
        "native_language": "",
        "role_anchor": "",
        "occupation": "",
        "industry": "",
        "education_level": "",
        "marital_status": "",
        "timezone": "",
    }


def _empty_capability() -> dict[str, Any]:
    return {
        "cefr": "",
        "level_band": "",
        "bottleneck_for_goal": "",
        "listening": None,
        "speaking": None,
        "reading": None,
        "writing": None,
        "grammar": None,
        "vocabulary": None,
    }


def _merge_identity(target: dict, source: dict) -> None:
    for key in _empty_identity():
        val = (source.get(key) or "").strip()
        if val and not target.get(key):
            target[key] = val


def extract_from_story(story: str) -> dict[str, Any]:
    text = story.strip()
    identity = _empty_identity()
    capability = _empty_capability()
    growth = {"goal": "", "current_stage": "", "completed_milestones": []}
    scenario = {"primary_track": "", "current_scenario": "", "next_scenarios": []}

    if not text:
        return {"identity": identity, "capability": capability, "growth": growth, "scenario": scenario}

    lower = text.lower()

    for token, country in COUNTRY_HINTS.items():
        if token.lower() in lower:
            identity["country"] = country
            break

    for token, lang in LANG_HINTS.items():
        if token.lower() in lower:
            identity["native_language"] = lang
            break

    for pattern, occ in OCCUPATION_HINTS:
        if re.search(pattern, text, re.I):
            identity["occupation"] = occ
            break

    for pattern, goal in GOAL_HINTS:
        if re.search(pattern, text, re.I):
            growth["goal"] = goal
            scenario["primary_track"] = "Global Career"
            if "面试" in goal:
                growth["current_stage"] = "Interview"
                scenario["current_scenario"] = "Technical Interview"
            break

    age_match = AGE_PATTERN.search(text)
    if age_match:
        age = int(age_match.group(1))
        if age < 18:
            identity["age_range"] = "18岁以下"
        elif age < 25:
            identity["age_range"] = "18-24"
        elif age < 35:
            identity["age_range"] = "25-34"
        else:
            identity["age_range"] = "35+"

    cefr_match = CEFR_PATTERN.search(text)
    if cefr_match:
        capability["cefr"] = cefr_match.group(1).upper()

    name_match = NAME_PATTERN.search(text)
    if name_match:
        identity["name"] = name_match.group(1)

    for city, country in CITY_COUNTRY.items():
        if city in text:
            identity["city"] = city
            if not identity["country"]:
                identity["country"] = country
            if not identity.get("region_anchor"):
                identity["region_anchor"] = country
            break

    for pattern, edu in EDUCATION_HINTS:
        if re.search(pattern, text, re.I):
            identity["education_level"] = edu
            break

    for pattern, status in MARITAL_HINTS:
        if re.search(pattern, text, re.I):
            identity["marital_status"] = status
            break

    if not identity["city"]:
        city_match = re.search(r"(?:住在|位于|来自)([\u4e00-\u9fa5]{2,4})", text)
        if city_match:
            identity["city"] = city_match.group(1)

    for match in SCORE_PATTERN.finditer(text):
        skill = SKILL_KEY_MAP.get(match.group(1))
        if skill:
            capability[skill] = min(100, int(match.group(2)))

    # 「70分」「40分」等裸分数按出现顺序映射到 听力/口语（启发式）
    bare_scores = [int(n) for n in re.findall(r"(\d{1,3})\s*分", text)]
    skill_order = ["listening", "speaking", "reading", "writing"]
    for i, score in enumerate(bare_scores):
        if i < len(skill_order) and capability.get(skill_order[i]) is None:
            capability[skill_order[i]] = min(100, score)

    from field_clusters import normalize_timeline

    if TIMELINE_PATTERN.search(text) or re.search(r"多久|几个月|之内|期限", text):
        norm = normalize_timeline(text)
        if norm:
            growth["timeline_urgency"] = norm

    for pattern, market in TARGET_MARKET_HINTS:
        if re.search(pattern, text, re.I):
            scenario["target_market"] = market
            break

    if re.search(r"口语.{0,6}(弱|差|不行|不好)", text):
        if not capability.get("bottleneck_for_goal") or capability["bottleneck_for_goal"] == "unknown":
            capability["bottleneck_for_goal"] = "speaking"
    if re.search(r"面试", text) and not scenario.get("interview_type"):
        if re.search(r"技术", text):
            scenario["interview_type"] = "技术深挖"
        else:
            scenario["interview_type"] = "混合"

    if identity["city"] in CITY_COUNTRY and not identity["country"]:
        identity["country"] = CITY_COUNTRY[identity["city"]]

    if identity["country"] == "中国" and not identity["timezone"]:
        identity["timezone"] = "Asia/Shanghai"

    if identity["country"] and not identity.get("region_anchor"):
        identity["region_anchor"] = identity["country"]
    if identity["occupation"] and not identity.get("role_anchor"):
        if identity["occupation"] == "学生":
            identity["role_anchor"] = "student"
        else:
            identity["role_anchor"] = "employed"
    if capability["cefr"] and not capability.get("level_band"):
        cefr_map = {
            "A1": "beginner", "A2": "elementary", "B1": "intermediate",
            "B2": "upper_intermediate", "C1": "advanced", "C2": "advanced",
        }
        capability["level_band"] = cefr_map.get(capability["cefr"], "")
    if capability.get("speaking") is not None:
        speaking = coerce_skill_score(capability["speaking"])
        if speaking is not None:
            capability["speaking"] = speaking
            if speaking < 60 and not capability.get("bottleneck_for_goal"):
                capability["bottleneck_for_goal"] = "speaking"
    elif capability.get("listening") is not None:
        listening = coerce_skill_score(capability["listening"])
        if listening is not None:
            capability["listening"] = listening
            if listening < 60 and not capability.get("bottleneck_for_goal"):
                capability["bottleneck_for_goal"] = "listening"

    return {
        "identity": identity,
        "capability": capability,
        "growth": growth,
        "scenario": scenario,
    }


def infer_geography(text: str) -> dict[str, Any] | None:
    """从文本识别城市/国家，返回 identity patch。"""
    raw = text.strip()
    if not raw:
        return None

    identity: dict[str, str] = {}

    for city, country in CITY_COUNTRY.items():
        if city in raw or raw == city:
            identity["city"] = city
            identity["country"] = country
            identity["region_anchor"] = country
            if country == "中国":
                identity["timezone"] = "Asia/Shanghai"
            return {"identity": identity}

    lower = raw.lower()
    for token, country in COUNTRY_HINTS.items():
        if token.lower() in lower or raw == country:
            identity["country"] = country
            identity["region_anchor"] = country
            if country == "中国":
                identity["timezone"] = "Asia/Shanghai"
            return {"identity": identity}

    return None


def extract_story(story: str) -> tuple[dict[str, Any], str]:
    """抽取故事字段：优先 LLM，失败则启发式。返回 (data, method)。"""
    from llm_extract import try_llm_extract

    llm_data = try_llm_extract(story)
    if llm_data:
        return llm_data, "llm"
    return extract_from_story(story), "heuristic"


def merge_twin(existing: dict | None, patch: dict) -> dict:
    twin = existing or {
        "identity": _empty_identity(),
        "capability": _empty_capability(),
        "growth": {
            "goal": "",
            "current_stage": "",
            "timeline_urgency": "",
            "deadline": "",
            "completed_milestones": [],
        },
        "scenario": {
            "primary_track": "",
            "current_scenario": "",
            "interview_type": "",
            "target_market": "",
            "target_exam": "",
            "target_score_band": "",
            "work_mode": "",
            "next_scenarios": [],
        },
        "learning": {},
        "behavior": {},
    }

    if patch.get("identity"):
        _merge_identity(twin["identity"], patch["identity"])
        if patch["identity"].get("country") and not twin["identity"].get("region_anchor"):
            twin["identity"]["region_anchor"] = patch["identity"]["country"]
        if patch["identity"].get("region_anchor") and not twin["identity"].get("country"):
            twin["identity"]["country"] = patch["identity"]["region_anchor"]
    if patch.get("growth"):
        for key, val in patch["growth"].items():
            if val is not None and val != "" and not isinstance(val, list):
                twin["growth"][key] = val.strip() if isinstance(val, str) else val
    if patch.get("scenario"):
        for key, val in patch["scenario"].items():
            if val is not None and val != "" and not isinstance(val, list):
                twin["scenario"][key] = val.strip() if isinstance(val, str) else val
    if patch.get("capability"):
        for key, val in patch["capability"].items():
            if val is None or val == "":
                continue
            if key in SKILL_SCORE_KEYS:
                val = coerce_skill_score(val)
            twin["capability"][key] = val

    return twin


def merge_twin_fill_empty(existing: dict | None, patch: dict) -> dict:
    """合并 patch，仅填充 twin 中仍为空的字段（不覆盖已有值）。"""
    twin = merge_twin(existing, {})

    if patch.get("identity"):
        _merge_identity(twin["identity"], patch["identity"])
        ident = patch["identity"]
        if ident.get("country") and not twin["identity"].get("region_anchor"):
            if not twin["identity"].get("region_anchor"):
                twin["identity"]["region_anchor"] = ident["country"]
        if ident.get("region_anchor") and not twin["identity"].get("country"):
            if not twin["identity"].get("country"):
                twin["identity"]["country"] = ident["region_anchor"]

    if patch.get("growth"):
        for key, val in patch["growth"].items():
            if val is None or val == "" or isinstance(val, list):
                continue
            cur = twin["growth"].get(key)
            if cur is None or (isinstance(cur, str) and not cur.strip()):
                twin["growth"][key] = val.strip() if isinstance(val, str) else val

    if patch.get("scenario"):
        for key, val in patch["scenario"].items():
            if val is None or val == "" or isinstance(val, list):
                continue
            cur = twin["scenario"].get(key)
            if cur is None or (isinstance(cur, str) and not cur.strip()):
                twin["scenario"][key] = val.strip() if isinstance(val, str) else val

    if patch.get("capability"):
        for key, val in patch["capability"].items():
            if val is None or val == "":
                continue
            if key in SKILL_SCORE_KEYS:
                val = coerce_skill_score(val)
            cur = twin["capability"].get(key)
            if cur is None or (isinstance(cur, str) and not cur.strip()):
                twin["capability"][key] = val

    return twin
