"""用户输入与 LLM 场景分层解析。"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

_SCENE_PARSE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "scene_parse.py"
_spec = importlib.util.spec_from_file_location("demo_goal_image_scene_parse", _SCENE_PARSE_PATH)
assert _spec and _spec.loader
_scene_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_scene_mod)
SCENE_PARSE_SYSTEM = _scene_mod.SCENE_PARSE_SYSTEM
SCENE_PARSE_USER = _scene_mod.SCENE_PARSE_USER

try:
    from _lib.llm import get_client, is_llm_available
except ImportError:  # pragma: no cover
    get_client = None  # type: ignore
    is_llm_available = lambda: False  # type: ignore

TEMPLATES = ("scroll_follow", "zoom_in", "parallax_horizontal")
TEXT_POSITIONS = ("top", "center", "bottom", "top_left", "bottom_right")
TEXT_REVEALS = ("early", "mid", "late")
TEXT_ROLES = ("title", "dialogue", "narration", "sfx", "none")

REQUIRED_KEYS = (
    "visual_style",
    "background_prompt",
    "subject_prompt",
    "text_content",
    "text_style",
    "text_role",
    "text_position",
    "text_reveal",
    "cinematic_template",
    "scene_description",
)


DEFAULT_VISUAL_STYLE = "日系手绘插画，柔和粉彩，细线描边，温暖治愈感"


def parse_user_input(user_input: str) -> dict[str, Any]:
    empty = {
        "sentence": "",
        "template": None,
        "mode": "series",
        "visual_style": "",
        "panel_count": 5,
    }
    if not user_input or not user_input.strip():
        return empty
    try:
        data = json.loads(user_input)
        if isinstance(data, dict):
            sentence = str(data.get("sentence") or data.get("prompt") or "").strip()
            template = data.get("template") or data.get("cinematic_template")
            if template and template not in TEMPLATES:
                template = None
            mode = data.get("mode") or "series"
            if mode not in ("series", "single"):
                mode = "series"
            visual_style = str(data.get("visual_style") or "").strip()
            panel_count = int(data.get("panel_count") or 5)
            return {
                "sentence": sentence,
                "template": template,
                "mode": mode,
                "visual_style": visual_style,
                "panel_count": panel_count,
            }
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return {
        "sentence": user_input.strip(),
        "template": None,
        "mode": "series",
        "visual_style": "",
        "panel_count": 5,
    }


def _extract_text_from_sentence(sentence: str) -> str:
    for pattern in (
        r"文字[：:]\s*([^\s，,。.]+)",
        r"标题[：:]\s*([^\s，,。.]+)",
        r"「([^」]+)」",
        r'"([^"]+)"',
    ):
        match = re.search(pattern, sentence)
        if match:
            return match.group(1).strip()
    parts = re.split(r"[，,。]", sentence)
    return (parts[-1] if parts else sentence).strip()[:8]


def _coerce_show_text(raw: dict[str, Any], text_content: str) -> bool:
    if "show_text" in raw:
        val = raw["show_text"]
        if isinstance(val, bool):
            return val
        if str(val).lower() in ("false", "0", "no"):
            return False
        return bool(val)
    return bool(text_content.strip())


def _normalize_text_overlay(raw: dict[str, Any], sentence: str) -> dict[str, Any]:
    content = str(raw.get("text_content") or "").strip()
    show = _coerce_show_text(raw, content)
    if not show:
        content = ""
    role = str(raw.get("text_role") or ("none" if not show else "narration")).strip().lower()
    if role not in TEXT_ROLES:
        role = "narration" if show else "none"
    style = str(raw.get("text_style") or "").strip()
    if show and not style:
        style = {
            "title": "大号手绘标题，白色粗体描边",
            "dialogue": "中号对话字，白色带深色描边",
            "narration": "小号半透明旁白，居中",
            "sfx": "大号拟声字，动感描边",
        }.get(role, "手绘风格文字，白色描边")
    position = str(raw.get("text_position") or "top").strip().lower()
    if position not in TEXT_POSITIONS:
        position = "center" if role == "dialogue" else "top"
    reveal = str(raw.get("text_reveal") or "late").strip().lower()
    if reveal not in TEXT_REVEALS:
        reveal = "early" if role == "title" else "late"
    if show and not content:
        # LLM 标记要显示文字但未给内容时，从叙事提炼短语
        scene = sentence.strip(" ，,")[:12]
        content = scene[:6] if scene else "…"
    return {
        "show_text": show,
        "text_content": content,
        "text_role": role,
        "text_style": style,
        "text_position": position,
        "text_reveal": reveal,
    }


def _fallback_plan(sentence: str, template: str | None = None) -> dict[str, Any]:
    scene = sentence.strip(" ，,")
    style = DEFAULT_VISUAL_STYLE
    text_overlay = _normalize_text_overlay(
        {
            "show_text": True,
            "text_content": scene[:6] if scene else "",
            "text_role": "title",
            "text_style": "大号手绘标题，白色粗体描边，偏上",
            "text_position": "top",
            "text_reveal": "mid",
        },
        sentence,
    )
    return {
        "visual_style": style,
        "background_prompt": (
            f"{style}。{scene}，16:9 宽幅空镜远景，无人物，only empty scenery, illustration background"
        ),
        "subject_prompt": (
            f"{style}。{scene}，仅主体半身或背影，"
            f"solid chroma key green background #00FF00, flat green screen, centered cutout"
        ),
        **text_overlay,
        "cinematic_template": template or "scroll_follow",
        "scene_description": "背景固定，主体随滚动移动",
    }


def _normalize_plan(raw: dict[str, Any], sentence: str, template: str | None) -> dict[str, Any]:
    plan = {key: str(raw.get(key) or "").strip() for key in REQUIRED_KEYS}
    plan.update(_normalize_text_overlay(raw, sentence))
    style = plan["visual_style"] or DEFAULT_VISUAL_STYLE
    if plan["cinematic_template"] not in TEMPLATES:
        plan["cinematic_template"] = template or "scroll_follow"
    if not plan["background_prompt"]:
        plan["background_prompt"] = _fallback_plan(sentence, template)["background_prompt"]
    if not plan["subject_prompt"]:
        plan["subject_prompt"] = _fallback_plan(sentence, template)["subject_prompt"]
    if not plan["scene_description"]:
        plan["scene_description"] = _fallback_plan(sentence, template)["scene_description"]
    if not plan["visual_style"]:
        plan["visual_style"] = style
    if "#00FF00" not in plan["subject_prompt"] and "green screen" not in plan["subject_prompt"].lower():
        plan["subject_prompt"] += "，solid chroma key green #00FF00 flat green screen background"
    if style not in plan["subject_prompt"]:
        plan["subject_prompt"] = f"{style}。{plan['subject_prompt']}"
    if style not in plan["background_prompt"]:
        plan["background_prompt"] = f"{style}。{plan['background_prompt']}"
    return plan


def parse_scene_plan(sentence: str, template: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """返回 (scene_plan, meta)。"""
    meta: dict[str, Any] = {"parse_source": "fallback"}

    if not sentence.strip():
        return _fallback_plan("", template), meta

    if is_llm_available():
        client = get_client() if get_client else None
        if client is not None:
            try:
                raw = client.chat_json(
                    SCENE_PARSE_USER.format(sentence=sentence),
                    system=SCENE_PARSE_SYSTEM,
                )
                plan = _normalize_plan(raw, sentence, template)
                meta["parse_source"] = "llm"
                return plan, meta
            except Exception as exc:  # noqa: BLE001
                meta["parse_error"] = str(exc)

    plan = _fallback_plan(sentence, template)
    return plan, meta
