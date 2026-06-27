"""5 幕故事分镜解析。"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

from pipeline.parse import (
    DEFAULT_VISUAL_STYLE,
    TEMPLATES,
    _normalize_text_overlay,
)

_STORYBOARD_PATH = Path(__file__).resolve().parent.parent / "prompts" / "storyboard_parse.py"
_spec = importlib.util.spec_from_file_location("demo_goal_image_storyboard", _STORYBOARD_PATH)
assert _spec and _spec.loader
_story_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_story_mod)

DEFAULT_PANEL_COUNT = _story_mod.DEFAULT_PANEL_COUNT
STORYBOARD_PARSE_SYSTEM = _story_mod.STORYBOARD_PARSE_SYSTEM
STORYBOARD_PARSE_USER = _story_mod.STORYBOARD_PARSE_USER

try:
    from _lib.llm import get_client, is_llm_available
except ImportError:  # pragma: no cover
    get_client = None  # type: ignore
    is_llm_available = lambda: False  # type: ignore

BEAT_ARCS = ("启程", "途中", "深入", "转折", "抵达")
GREEN_SUFFIX = "，solid chroma key green #00FF00 flat green screen, no shadow on background, centered"

# 无 LLM 时各幕文字叠层策略（模拟「编剧」决策）
ARC_TEXT_PRESETS: dict[str, dict[str, Any]] = {
    "启程": {
        "show_text": True,
        "text_content": "出发",
        "text_role": "title",
        "text_style": "大号手绘标题，白色粗体描边",
        "text_position": "top",
        "text_reveal": "early",
    },
    "途中": {
        "show_text": False,
        "text_content": "",
        "text_role": "none",
        "text_style": "",
        "text_position": "center",
        "text_reveal": "mid",
    },
    "深入": {
        "show_text": True,
        "text_content": "继续走",
        "text_role": "narration",
        "text_style": "小号半透明旁白，手绘感",
        "text_position": "bottom",
        "text_reveal": "late",
    },
    "转折": {
        "show_text": True,
        "text_content": "嘿！",
        "text_role": "dialogue",
        "text_style": "中号对话字，白色描边，略像气泡",
        "text_position": "top_left",
        "text_reveal": "mid",
    },
    "抵达": {
        "show_text": True,
        "text_content": "到了",
        "text_role": "title",
        "text_style": "大号标题，暖色描边",
        "text_position": "center",
        "text_reveal": "late",
    },
}


def _ensure_green(prompt: str) -> str:
    low = prompt.lower()
    if "#00ff00" in low or "green screen" in low:
        return prompt
    return prompt + GREEN_SUFFIX


def _scene_from_sentence(sentence: str) -> str:
    return re.sub(r"文字[：:][^\s，,。.]+", "", sentence).strip(" ，,")


def _fallback_beat(
    beat_id: int,
    arc: str,
    sentence: str,
    style: str,
    character: str,
) -> dict[str, Any]:
    scene = _scene_from_sentence(sentence)
    preset = ARC_TEXT_PRESETS.get(arc, {"show_text": False, "text_content": "", "text_role": "none"})
    text_fields = _normalize_text_overlay(preset, sentence)
    return {
        "id": beat_id,
        "narration": f"第{beat_id}幕·{arc}：{scene}",
        "background_prompt": (
            f"{style}。{scene}，第{beat_id}幕·{arc}，16:9 宽幅空镜手绘背景，"
            f"无人物 no people, illustration background only"
        ),
        "subject_prompt": _ensure_green(
            f"{style}。{character}，第{beat_id}幕·{arc}，{scene}，"
            f"hand-drawn illustration character only, same character design"
        ),
        **text_fields,
        "scene_description": f"背景固定，主体随滚动·{arc}",
        "cinematic_template": "scroll_follow",
    }


def _fallback_storyboard(sentence: str, visual_style: str | None = None) -> dict[str, Any]:
    style = visual_style or DEFAULT_VISUAL_STYLE
    scene = _scene_from_sentence(sentence)
    character = "同一主角：手绘插画风格远行者，浅蓝外套，大背包，侧脸或背影"
    beats = [
        _fallback_beat(i + 1, BEAT_ARCS[i], sentence, style, character)
        for i in range(DEFAULT_PANEL_COUNT)
    ]
    return {
        "title": scene[:14] or "连续故事",
        "visual_style": style,
        "character_anchor": character,
        "beats": beats,
    }


def _normalize_beat(
    raw: dict[str, Any],
    beat_id: int,
    style: str,
    character: str,
    sentence: str,
) -> dict[str, Any]:
    arc = BEAT_ARCS[beat_id - 1] if beat_id <= len(BEAT_ARCS) else f"幕{beat_id}"
    text_fields = _normalize_text_overlay(raw, sentence)
    beat = {
        "id": beat_id,
        "narration": str(raw.get("narration") or f"第{beat_id}幕·{arc}").strip(),
        "background_prompt": str(raw.get("background_prompt") or "").strip(),
        "subject_prompt": str(raw.get("subject_prompt") or "").strip(),
        **text_fields,
        "scene_description": str(raw.get("scene_description") or "").strip(),
        "cinematic_template": str(raw.get("cinematic_template") or "scroll_follow").strip(),
    }
    if beat["cinematic_template"] not in TEMPLATES:
        beat["cinematic_template"] = "scroll_follow"
    if not beat["background_prompt"]:
        beat["background_prompt"] = _fallback_beat(beat_id, arc, sentence, style, character)[
            "background_prompt"
        ]
    if not beat["subject_prompt"]:
        beat["subject_prompt"] = _fallback_beat(beat_id, arc, sentence, style, character)["subject_prompt"]
    if not beat["scene_description"]:
        beat["scene_description"] = f"背景固定，主体随滚动·{arc}"
    if style not in beat["background_prompt"]:
        beat["background_prompt"] = f"{style}。{beat['background_prompt']}"
    if character not in beat["subject_prompt"]:
        beat["subject_prompt"] = f"{style}。{character}。{beat['subject_prompt']}"
    beat["subject_prompt"] = _ensure_green(beat["subject_prompt"])
    return beat


def _normalize_storyboard(
    raw: dict[str, Any],
    sentence: str,
    visual_style: str | None,
) -> dict[str, Any]:
    style = str(raw.get("visual_style") or visual_style or DEFAULT_VISUAL_STYLE).strip()
    character = str(
        raw.get("character_anchor") or "手绘插画主角，外貌在各幕保持一致"
    ).strip()
    scene = _scene_from_sentence(sentence)
    title = str(raw.get("title") or scene[:14] or "连续故事").strip()

    raw_beats = raw.get("beats")
    if not isinstance(raw_beats, list):
        raw_beats = []

    beats: list[dict[str, Any]] = []
    for i in range(DEFAULT_PANEL_COUNT):
        src = raw_beats[i] if i < len(raw_beats) and isinstance(raw_beats[i], dict) else {}
        beats.append(_normalize_beat(src, i + 1, style, character, sentence))

    return {
        "title": title,
        "visual_style": style,
        "character_anchor": character,
        "beats": beats,
    }


def parse_storyboard(
    sentence: str,
    visual_style: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    meta: dict[str, Any] = {"parse_source": "fallback", "panel_count": DEFAULT_PANEL_COUNT}

    if not sentence.strip():
        return _fallback_storyboard(sentence, visual_style), meta

    if is_llm_available():
        client = get_client() if get_client else None
        if client is not None:
            try:
                raw = client.chat_json(
                    STORYBOARD_PARSE_USER.format(sentence=sentence),
                    system=STORYBOARD_PARSE_SYSTEM,
                )
                board = _normalize_storyboard(raw, sentence, visual_style)
                meta["parse_source"] = "llm"
                return board, meta
            except Exception as exc:  # noqa: BLE001
                meta["parse_error"] = str(exc)

    return _fallback_storyboard(sentence, visual_style), meta


def beat_to_plan(storyboard: dict[str, Any], beat: dict[str, Any]) -> dict[str, Any]:
    """将单幕 beat 转为 build_layer_assets 可用的 plan。"""
    return {
        "visual_style": storyboard["visual_style"],
        "background_prompt": beat["background_prompt"],
        "subject_prompt": beat["subject_prompt"],
        "show_text": beat.get("show_text", False),
        "text_content": beat.get("text_content") or "",
        "text_role": beat.get("text_role") or "none",
        "text_style": beat.get("text_style") or "",
        "text_position": beat.get("text_position") or "top",
        "text_reveal": beat.get("text_reveal") or "late",
        "cinematic_template": beat.get("cinematic_template") or "scroll_follow",
        "scene_description": beat.get("scene_description") or beat.get("narration") or "",
    }
