"""连续底图长卷：解析与规划。"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

from pipeline.parse import DEFAULT_VISUAL_STYLE, _normalize_text_overlay

_STRIP_PATH = Path(__file__).resolve().parent.parent / "prompts" / "strip_parse.py"
_spec = importlib.util.spec_from_file_location("demo_goal_image_strip", _STRIP_PATH)
assert _spec and _spec.loader
_strip_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_strip_mod)

MIN_TILES = _strip_mod.MIN_TILES
MAX_TILES = _strip_mod.MAX_TILES
MIN_SPRITES = _strip_mod.MIN_SPRITES
MAX_SPRITES = _strip_mod.MAX_SPRITES
STRIP_PARSE_SYSTEM = _strip_mod.STRIP_PARSE_SYSTEM
STRIP_PARSE_USER = _strip_mod.STRIP_PARSE_USER

GREEN_SUFFIX = "，solid chroma key green #00FF00 flat green screen, no shadow on background, centered"
PARALLAX_MODES = ("scroll_follow", "slow", "fast", "fixed")

try:
    from _lib.llm import get_client, is_llm_available
except ImportError:  # pragma: no cover
    get_client = None  # type: ignore
    is_llm_available = lambda: False  # type: ignore

FALLBACK_SCENES = (
    ("山脚晨雾", "清晨山间小路起点，薄雾，远山"),
    ("林间石阶", "树林中的石阶小径向下延伸，光斑"),
    ("溪谷小桥", "山谷小溪木桥，水流潺潺"),
    ("开阔坡道", "山坡俯瞰远方，路径继续向前"),
    ("驿站近景", "路边驿站或站牌，旅途中段"),
    ("暮色归途", "傍晚暖光，路通向远方"),
)

FALLBACK_SPRITE_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "label": "启程",
        "pose": "侧身行走，背着包，小比例全身",
        "anchor_tile": 1,
        "anchor_y": 0.72,
        "anchor_x": 0.42,
        "scale": 0.34,
        "parallax": "scroll_follow",
        "scroll_start": 0.0,
        "scroll_end": 0.4,
        "text": {"show_text": True, "text_content": "出发", "text_role": "title", "text_reveal": "early"},
    },
    {
        "label": "驻足",
        "pose": "停下远望，半身",
        "anchor_tile": 2,
        "anchor_y": 0.58,
        "anchor_x": 0.55,
        "scale": 0.3,
        "parallax": "slow",
        "scroll_start": 0.22,
        "scroll_end": 0.58,
        "text": {"show_text": False},
    },
    {
        "label": "招呼",
        "pose": "举手打招呼，活泼姿势",
        "anchor_tile": 3,
        "anchor_y": 0.52,
        "anchor_x": 0.38,
        "scale": 0.28,
        "parallax": "fast",
        "scroll_start": 0.42,
        "scroll_end": 0.72,
        "text": {"show_text": True, "text_content": "嘿！", "text_role": "dialogue", "text_reveal": "mid"},
    },
    {
        "label": "归途",
        "pose": "背影继续向北，渐行渐远",
        "anchor_tile": 5,
        "anchor_y": 0.65,
        "anchor_x": 0.5,
        "scale": 0.32,
        "parallax": "scroll_follow",
        "scroll_start": 0.58,
        "scroll_end": 1.0,
        "text": {"show_text": True, "text_content": "到了", "text_role": "title", "text_reveal": "late"},
    },
)


def _scene_from_sentence(sentence: str) -> str:
    return re.sub(r"文字[：:][^\s，,。.]+", "", sentence).strip(" ，,")


def _character_from_sentence(sentence: str) -> str:
    scene = _scene_from_sentence(sentence)
    for pattern in (
        r"(远行者[^，,。]*)",
        r"(少年[^，,。]*)",
        r"(旅人[^，,。]*)",
        r"(女孩[^，,。]*)",
        r"(男孩[^，,。]*)",
    ):
        match = re.search(pattern, scene)
        if match:
            return match.group(1).strip()
    return scene[:12] or "故事主角"


def _ensure_green(prompt: str) -> str:
    low = prompt.lower()
    if "#00ff00" in low or "green screen" in low:
        return prompt
    return prompt + GREEN_SUFFIX


def _clamp_tile_count(n: int) -> int:
    return max(MIN_TILES, min(MAX_TILES, n))


def _clamp_sprite_count(n: int) -> int:
    return max(MIN_SPRITES, min(MAX_SPRITES, n))


def _clamp01(value: Any, default: float = 0.5) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, v))


def _fallback_tiles(sentence: str, style: str, count: int) -> list[dict[str, Any]]:
    scene = _scene_from_sentence(sentence) or "远行者旅途"
    count = _clamp_tile_count(count)
    tiles: list[dict[str, Any]] = []
    for i in range(count):
        name, desc = FALLBACK_SCENES[i % len(FALLBACK_SCENES)]
        seam = (
            f"路径与色调与下一段衔接，{FALLBACK_SCENES[(i + 1) % len(FALLBACK_SCENES)][1]}"
            if i < count - 1
            else "旅途终点，画面收束"
        )
        tiles.append(
            {
                "index": i + 1,
                "scene": name,
                "prompt": f"{style}。{scene}，{desc}，手绘插画空镜背景，无人物",
                "height_weight": 1.0,
                "seam_bottom": seam,
            }
        )
    return tiles


def _fallback_sprites(
    sentence: str,
    style: str,
    character: str,
    tile_count: int,
) -> list[dict[str, Any]]:
    count = _clamp_sprite_count(min(MAX_SPRITES, max(MIN_SPRITES, tile_count // 2 + 1)))
    presets = list(FALLBACK_SPRITE_PRESETS)[:count]
    sprites: list[dict[str, Any]] = []
    for i, preset in enumerate(presets):
        anchor_tile = min(tile_count, max(1, int(preset["anchor_tile"])))
        if anchor_tile > tile_count:
            anchor_tile = max(1, tile_count - (len(presets) - i - 1))
        text_fields = _normalize_text_overlay(preset.get("text") or {}, sentence)
        sprites.append(
            _normalize_sprite(
                {
                    "id": i + 1,
                    "label": preset["label"],
                    "prompt": f"{style}。{character}，{preset['pose']}，仅角色 cutout",
                    **preset,
                    **text_fields,
                },
                i + 1,
                style,
                character,
                sentence,
                tile_count,
            )
        )
    return sprites


def _normalize_tile(raw: dict[str, Any], index: int, style: str, sentence: str) -> dict[str, Any]:
    scene = str(raw.get("scene") or f"第{index}段").strip()
    prompt = str(raw.get("prompt") or "").strip()
    if not prompt:
        prompt = f"{style}。{_scene_from_sentence(sentence)}，{scene}，手绘空镜无人物"
    elif style not in prompt:
        prompt = f"{style}。{prompt}"
    if "无人物" not in prompt and "no people" not in prompt.lower():
        prompt += "，无人物 no people empty scene"

    weight = raw.get("height_weight", 1.0)
    try:
        weight = float(weight)
    except (TypeError, ValueError):
        weight = 1.0
    weight = max(0.6, min(1.5, weight))

    return {
        "index": index,
        "scene": scene,
        "prompt": prompt,
        "height_weight": weight,
        "seam_bottom": str(raw.get("seam_bottom") or "").strip(),
    }


def _normalize_sprite(
    raw: dict[str, Any],
    index: int,
    style: str,
    character: str,
    sentence: str,
    tile_count: int,
) -> dict[str, Any]:
    label = str(raw.get("label") or f"精灵{index}").strip()
    prompt = str(raw.get("prompt") or "").strip()
    if not prompt:
        prompt = f"{style}。{character}，{label}，小比例手绘角色"
    if character and character not in prompt:
        prompt = f"{character}，{prompt}"
    if style not in prompt:
        prompt = f"{style}。{prompt}"
    prompt = _ensure_green(prompt)
    if "小比例" not in prompt and "small scale" not in prompt.lower():
        prompt += "，small scale comic character cutout only"

    try:
        anchor_tile = int(raw.get("anchor_tile") or index)
    except (TypeError, ValueError):
        anchor_tile = index
    anchor_tile = max(1, min(tile_count, anchor_tile))

    try:
        scale = float(raw.get("scale") or 0.32)
    except (TypeError, ValueError):
        scale = 0.32
    scale = max(0.18, min(0.5, scale))

    parallax = str(raw.get("parallax") or "scroll_follow").strip().lower()
    if parallax not in PARALLAX_MODES:
        parallax = "scroll_follow"

    try:
        z_index = int(raw.get("z_index") or (10 + index))
    except (TypeError, ValueError):
        z_index = 10 + index

    text_fields = _normalize_text_overlay(raw, sentence)

    return {
        "id": index,
        "label": label,
        "prompt": prompt,
        "anchor_tile": anchor_tile,
        "anchor_y": _clamp01(raw.get("anchor_y"), 0.6),
        "anchor_x": _clamp01(raw.get("anchor_x"), 0.5),
        "scale": scale,
        "parallax": parallax,
        "scroll_start": _clamp01(raw.get("scroll_start"), 0.0),
        "scroll_end": _clamp01(raw.get("scroll_end"), 1.0),
        "z_index": z_index,
        **text_fields,
    }


def _normalize_sprites(
    raw_sprites: Any,
    sentence: str,
    style: str,
    character: str,
    tile_count: int,
) -> list[dict[str, Any]]:
    if not isinstance(raw_sprites, list) or len(raw_sprites) < MIN_SPRITES:
        return _fallback_sprites(sentence, style, character, tile_count)

    count = _clamp_sprite_count(len(raw_sprites))
    sprites: list[dict[str, Any]] = []
    for i in range(count):
        src = raw_sprites[i] if i < len(raw_sprites) and isinstance(raw_sprites[i], dict) else {}
        sprites.append(_normalize_sprite(src, i + 1, style, character, sentence, tile_count))

    for sprite in sprites:
        if sprite["scroll_end"] <= sprite["scroll_start"]:
            sprite["scroll_end"] = min(1.0, sprite["scroll_start"] + 0.25)

    return sprites


def _normalize_strip_plan(
    raw: dict[str, Any],
    sentence: str,
    visual_style: str | None,
) -> dict[str, Any]:
    style = str(raw.get("visual_style") or visual_style or DEFAULT_VISUAL_STYLE).strip()
    title = str(raw.get("title") or _scene_from_sentence(sentence)[:16] or "连续长卷").strip()
    character = str(raw.get("character_anchor") or _character_from_sentence(sentence)).strip()

    raw_tiles = raw.get("background_tiles")
    if not isinstance(raw_tiles, list) or len(raw_tiles) < MIN_TILES:
        count = _clamp_tile_count(len(raw_tiles) if isinstance(raw_tiles, list) and raw_tiles else MIN_TILES)
        tiles = _fallback_tiles(sentence, style, count)
    else:
        count = _clamp_tile_count(len(raw_tiles))
        tiles = []
        for i in range(count):
            src = raw_tiles[i] if i < len(raw_tiles) and isinstance(raw_tiles[i], dict) else {}
            tiles.append(_normalize_tile(src, i + 1, style, sentence))

    sprites = _normalize_sprites(raw.get("sprites"), sentence, style, character, len(tiles))

    try:
        scroll_screens = int(raw.get("estimated_scroll_screens") or len(tiles) + 1)
    except (TypeError, ValueError):
        scroll_screens = len(tiles) + 1
    scroll_screens = max(len(tiles), min(12, scroll_screens))

    return {
        "title": title,
        "visual_style": style,
        "character_anchor": character,
        "estimated_scroll_screens": scroll_screens,
        "background_tiles": tiles,
        "tile_count": len(tiles),
        "sprites": sprites,
        "sprite_count": len(sprites),
    }


def parse_strip_plan(
    sentence: str,
    visual_style: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    meta: dict[str, Any] = {"parse_source": "fallback", "mode": "continuous_strip"}

    if not sentence.strip():
        plan = _normalize_strip_plan({}, sentence, visual_style)
        return plan, meta

    if is_llm_available():
        client = get_client() if get_client else None
        if client is not None:
            try:
                raw = client.chat_json(
                    STRIP_PARSE_USER.format(sentence=sentence),
                    system=STRIP_PARSE_SYSTEM,
                )
                plan = _normalize_strip_plan(raw, sentence, visual_style)
                meta["parse_source"] = "llm"
                return plan, meta
            except Exception as exc:  # noqa: BLE001
                meta["parse_error"] = str(exc)

    plan = _normalize_strip_plan({"background_tiles": []}, sentence, visual_style)
    return plan, meta


def tile_generation_prompt(
    tile: dict[str, Any],
    style: str,
    prev_seam: str | None = None,
) -> str:
    parts = [tile["prompt"]]
    if prev_seam:
        parts.append(
            f"This segment continues directly below the previous scene. "
            f"The TOP edge must seamlessly match: {prev_seam}"
        )
    if tile.get("seam_bottom"):
        parts.append(f"The BOTTOM edge should end with: {tile['seam_bottom']}")
    parts.append("Single continuous hand-drawn illustration background, no people, no text")
    return " ".join(parts)


def sprite_generation_prompt(sprite: dict[str, Any], character_anchor: str) -> str:
    parts = [sprite["prompt"]]
    if character_anchor and character_anchor not in sprite["prompt"]:
        parts.insert(0, f"Same character as: {character_anchor}")
    parts.append("Single isolated hand-drawn character sprite, small comic scale, no scenery, no text")
    return " ".join(parts)
