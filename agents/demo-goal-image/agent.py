"""一句话生成电影感分层视差滚动 HTML（微信公众号可粘贴）。"""

from __future__ import annotations

import json
from typing import Any

from _lib.image import ImageConfig, is_image_api_available
from _lib.llm import is_llm_available

from pipeline.assets import build_layer_assets, build_strip_assets
from pipeline.parse import parse_scene_plan, parse_user_input
from pipeline.render import render_parallax_html, render_strip_scroll_html
from pipeline.strip import parse_strip_plan


def _run_single(
    sentence: str,
    template_override: str | None,
    image_cfg: ImageConfig,
    meta: dict[str, Any],
) -> dict[str, Any]:
    plan, parse_meta = parse_scene_plan(sentence, template_override)
    meta.update(parse_meta)
    meta["mode"] = "single"
    meta["template"] = plan["cinematic_template"]

    assets, asset_meta = build_layer_assets(plan, image_cfg)
    meta.update(asset_meta)

    html = render_parallax_html(plan, assets)
    meta["stages"].append("render_html")

    return {
        "output": html,
        "html": html,
        "sentence": sentence,
        "scene_plan": plan,
        "assets_preview": {
            "background": assets["background_data_uri"],
            "subject": assets["subject_data_uri"],
            "text": assets["text_data_uri"],
        },
        "meta": meta,
    }


def _run_series(
    sentence: str,
    visual_style: str | None,
    image_cfg: ImageConfig,
    meta: dict[str, Any],
) -> dict[str, Any]:
    """连续底图长卷模式。"""
    strip_plan, parse_meta = parse_strip_plan(sentence, visual_style or None)
    meta.update(parse_meta)
    meta["mode"] = "continuous_strip"
    meta["tile_count"] = strip_plan["tile_count"]
    meta["sprite_count"] = strip_plan.get("sprite_count", len(strip_plan.get("sprites", [])))

    strip_assets, asset_meta = build_strip_assets(strip_plan, image_cfg)
    meta.update(asset_meta)

    html = render_strip_scroll_html(strip_plan, strip_assets)
    meta["stages"].append("render_html")

    return {
        "output": html,
        "html": html,
        "sentence": sentence,
        "strip_plan": strip_plan,
        "tile_previews": strip_assets.get("tile_previews", []),
        "sprite_previews": strip_assets.get("sprites", []),
        "assets_preview": {
            "strip": strip_assets["strip_data_uri"],
            "strip_height": strip_assets["strip_height"],
            "strip_width": strip_assets["strip_width"],
            "sprites": [
                {"id": s["id"], "label": s.get("label"), "preview": s.get("preview")}
                for s in strip_assets.get("sprites", [])
            ],
        },
        "meta": meta,
    }


def run(user_input: str, **kwargs) -> dict:
    payload = parse_user_input(user_input)
    sentence = payload["sentence"]
    template_override = payload.get("template")
    mode = payload.get("mode") or "series"
    visual_style = (payload.get("visual_style") or "").strip() or None

    if not sentence:
        return {
            "output": "",
            "error": "请输入一句话描述故事场景",
            "meta": {
                "agent": "demo-goal-image",
                "llm_available": is_llm_available(),
                "image_available": is_image_api_available(),
            },
        }

    meta: dict[str, Any] = {
        "agent": "demo-goal-image",
        "llm_available": is_llm_available(),
        "image_available": is_image_api_available(),
    }

    try:
        image_cfg = ImageConfig.from_overrides(kwargs.get("image_config"))
        if mode == "single":
            return _run_single(sentence, template_override, image_cfg, meta)
        return _run_series(sentence, visual_style, image_cfg, meta)
    except Exception as exc:  # noqa: BLE001
        return {
            "output": "",
            "error": str(exc),
            "sentence": sentence,
            "meta": meta,
        }


if __name__ == "__main__":
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else "雨后山间小路，远行者背着包一路向北"
    print(json.dumps(run(text), ensure_ascii=False, indent=2))
