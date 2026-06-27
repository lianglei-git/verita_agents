"""素材生成：下载图片、去背景、文字 PNG、Base64。"""

from __future__ import annotations

import base64
import io
import logging
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from _lib.image import ImageConfig, get_image_client

logger = logging.getLogger(__name__)

BG_SIZE = "1344x768"
SUBJECT_SIZE = "1024x1024"

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
)

_CHROMA_GREEN = (0, 255, 0)


def _download_image(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "verita-agents/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _image_bytes_from_api_result(result: dict[str, Any]) -> bytes:
    if result.get("b64_json"):
        return base64.b64decode(result["b64_json"])
    url = result.get("url")
    if not url:
        raise RuntimeError("图像 API 未返回可用数据")
    return _download_image(url)


def _pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _color_dist(c1: tuple[int, ...], c2: tuple[int, ...]) -> float:
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2) ** 0.5


def _flood_transparent(img: Image.Image, seeds: list[tuple[int, int]], tolerance: float) -> Image.Image:
    """从种子点泛洪，相似色变透明（去除纯色/灰底边框）。"""
    rgba = img.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    visited: set[tuple[int, int]] = set()

    for sx, sy in seeds:
        if not (0 <= sx < width and 0 <= sy < height):
            continue
        seed_rgb = pixels[sx, sy][:3]
        queue: deque[tuple[int, int]] = deque([(sx, sy)])
        while queue:
            x, y = queue.popleft()
            if (x, y) in visited:
                continue
            if x < 0 or y < 0 or x >= width or y >= height:
                continue
            rgb = pixels[x, y][:3]
            if _color_dist(rgb, seed_rgb) > tolerance:
                continue
            visited.add((x, y))
            pixels[x, y] = (rgb[0], rgb[1], rgb[2], 0)
            queue.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    return rgba


def _chroma_key(img: Image.Image, key: tuple[int, int, int], tolerance: float) -> Image.Image:
    rgba = img.convert("RGBA")
    pixels = rgba.load()
    kr, kg, kb = key
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if _color_dist((r, g, b), (kr, kg, kb)) <= tolerance:
                pixels[x, y] = (r, g, b, 0)
            elif key == _CHROMA_GREEN and g > 180 and g > r + 40 and g > b + 40:
                # 偏绿幕
                pixels[x, y] = (r, g, b, 0)
    return rgba


def _light_key(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if r > 200 and g > 200 and b > 200:
                pixels[x, y] = (r, g, b, 0)
    return rgba


def _trim_alpha(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _opaque_ratio(png_bytes: bytes) -> float:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    pixels = img.getdata()
    if not pixels:
        return 1.0
    opaque = sum(1 for p in pixels if p[3] > 16)
    return opaque / len(pixels)


def _remove_background(img_bytes: bytes) -> tuple[bytes, str]:
    """多层抠图：rembg → 绿幕 → 角点泛洪 → 浅色键。"""
    methods: list[str] = []

    try:
        from rembg import remove  # type: ignore

        out = remove(img_bytes)
        trimmed = _trim_alpha(out)
        if _opaque_ratio(trimmed) < 0.92:
            return trimmed, "rembg"
        methods.append("rembg_partial")
        img_bytes = trimmed
    except Exception as exc:  # noqa: BLE001
        logger.info("rembg unavailable (%s), using chroma/flood fallback", exc)

    img = Image.open(io.BytesIO(img_bytes))
    w, h = img.size

    # 绿幕键
    keyed = _chroma_key(img, _CHROMA_GREEN, tolerance=95)
    if _opaque_ratio(_png_bytes(keyed)) < 0.9:
        return _trim_alpha(_png_bytes(keyed)), "chroma_green"

    # 四角 + 四边中点泛洪（去除灰/白底）
    seeds = [
        (0, 0),
        (w - 1, 0),
        (0, h - 1),
        (w - 1, h - 1),
        (w // 2, 0),
        (w // 2, h - 1),
        (0, h // 2),
        (w - 1, h // 2),
    ]
    flooded = _flood_transparent(img, seeds, tolerance=42)
    if _opaque_ratio(_png_bytes(flooded)) < 0.88:
        return _trim_alpha(_png_bytes(flooded)), "flood_corners"

    # 浅色键 + 再泛洪
    lit = _light_key(img)
    flooded2 = _flood_transparent(lit, seeds, tolerance=36)
    trimmed = _trim_alpha(_png_bytes(flooded2))
    method = "+".join(methods + ["light_key", "flood"])
    return trimmed, method


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_text_png(
    text: str,
    style_hint: str = "",
    position: str = "top",
    role: str = "narration",
) -> bytes:
    if not text or not str(text).strip():
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    hint = (style_hint or "").lower()
    role = (role or "narration").lower()

    if any(k in hint for k in ("大", "标题", "large", "title")) or role == "title":
        font_size = 128
    elif any(k in hint for k in ("小", "旁白", "small")) or role == "narration":
        font_size = 72
    elif role == "sfx":
        font_size = 110
    else:
        font_size = 96

    fill = (255, 255, 255, 255)
    if any(k in hint for k in ("暖", "金", "黄")):
        fill = (255, 230, 180, 255)
    elif any(k in hint for k in ("半透明", "muted")):
        fill = (255, 255, 255, 190)

    canvas_w, canvas_h = 1200, 400
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _pick_font(font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pos = (position or "top").lower()
    if pos in ("top", "top_left", "top_right"):
        y = 36
    elif pos in ("bottom", "bottom_left", "bottom_right"):
        y = canvas_h - th - 36
    else:
        y = (canvas_h - th) // 2 - 10

    if pos.endswith("_left"):
        x = 80
    elif pos.endswith("_right"):
        x = canvas_w - tw - 80
    else:
        x = (canvas_w - tw) // 2

    shadow = (0, 0, 0, 140 if "半透明" not in hint else 90)
    draw.text((x + 3, y + 3), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _to_data_uri(raw_bytes: bytes, mime: str) -> str:
    encoded = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _to_b64(png_bytes: bytes) -> str:
    return base64.b64encode(png_bytes).decode("ascii")


def build_layer_assets(
    plan: dict[str, Any],
    image_cfg: ImageConfig | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """生成三层素材，返回 (assets, meta)。"""
    client = get_image_client(image_cfg)
    if client is None:
        raise RuntimeError("未配置图像 API（IMAGE_API_KEY / OPENAI_API_KEY）")

    meta: dict[str, Any] = {"stages": []}

    meta["stages"].append("generate_background")
    bg_result = client.generate(plan["background_prompt"], size=BG_SIZE)
    bg_raw = _image_bytes_from_api_result(bg_result)
    bg_png = Image.open(io.BytesIO(bg_raw)).convert("RGB")
    bg_buf = io.BytesIO()
    bg_png.save(bg_buf, format="JPEG", quality=88)
    bg_jpeg = bg_buf.getvalue()

    meta["stages"].append("generate_subject")
    subject_result = client.generate(plan["subject_prompt"], size=SUBJECT_SIZE)
    subject_raw = _image_bytes_from_api_result(subject_result)
    subject_png, cutout_method = _remove_background(subject_raw)
    meta["subject_cutout"] = cutout_method

    meta["stages"].append("render_text")
    show_text = plan.get("show_text", bool((plan.get("text_content") or "").strip()))
    if show_text:
        text_png = render_text_png(
            plan["text_content"],
            plan.get("text_style", ""),
            plan.get("text_position", "top"),
            plan.get("text_role", "narration"),
        )
    else:
        text_png = render_text_png("", "", "top", "none")

    assets = {
        "background_b64": _to_b64(bg_jpeg),
        "background_mime": "image/jpeg",
        "subject_b64": _to_b64(subject_png),
        "subject_mime": "image/png",
        "text_b64": _to_b64(text_png),
        "text_mime": "image/png",
        "background_data_uri": _to_data_uri(bg_jpeg, "image/jpeg"),
        "subject_data_uri": _to_data_uri(subject_png, "image/png"),
        "text_data_uri": _to_data_uri(text_png, "image/png"),
        "has_text": show_text,
        "text_role": plan.get("text_role"),
        "text_position": plan.get("text_position"),
        "text_reveal": plan.get("text_reveal"),
    }
    meta["stages"].append("encode_assets")
    return assets, meta


def build_series_assets(
    storyboard: dict[str, Any],
    image_cfg: ImageConfig | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """逐幕生成三层素材。"""
    from pipeline.storyboard import beat_to_plan

    meta: dict[str, Any] = {"stages": [], "beats_meta": []}
    beats_assets: list[dict[str, Any]] = []

    for beat in storyboard["beats"]:
        beat_id = beat["id"]
        meta["stages"].append(f"beat_{beat_id}_start")
        plan = beat_to_plan(storyboard, beat)
        assets, beat_meta = build_layer_assets(plan, image_cfg)
        beats_assets.append(
            {
                **assets,
                "beat_id": beat_id,
                "narration": beat.get("narration", ""),
                "text_content": beat.get("text_content", ""),
                "has_text": assets.get("has_text", beat.get("show_text", False)),
            }
        )
        meta["beats_meta"].append({"id": beat_id, **beat_meta})
        meta["stages"].append(f"beat_{beat_id}_done")

    meta["stages"].append("encode_series")
    return beats_assets, meta


TILE_WIDTH = 1344
STRIP_BLEND_PX = 28


def compute_strip_tile_offsets(heights: list[int], blend_px: int = STRIP_BLEND_PX) -> list[int]:
    """各 tile 顶部在拼接后画布中的 Y 偏移（与 stitch_tiles_vertical 逻辑一致）。"""
    if not heights:
        return []
    offsets = [0]
    for i in range(1, len(heights)):
        prev_h, cur_h = heights[i - 1], heights[i]
        overlap = min(blend_px, prev_h // 5, cur_h // 5)
        if overlap < 6:
            offsets.append(offsets[-1] + prev_h)
        else:
            offsets.append(offsets[-1] + prev_h - overlap)
    return offsets


def anchor_y_on_strip(
    tile_offsets: list[int],
    tile_heights: list[int],
    anchor_tile: int,
    anchor_y: float,
) -> float:
    idx = max(0, min(len(tile_offsets) - 1, anchor_tile - 1))
    height = tile_heights[idx] if idx < len(tile_heights) else 0
    return tile_offsets[idx] + _clamp01(anchor_y, 0.5) * height


def _clamp01(value: float, default: float = 0.5) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, v))


def stitch_tiles_vertical(images: list[Image.Image], blend_px: int = STRIP_BLEND_PX) -> Image.Image:
    """纵向拼接底图条，接缝处轻量羽化。"""
    if not images:
        raise ValueError("无底图 tile 可拼接")

    resized: list[Image.Image] = []
    for img in images:
        rgb = img.convert("RGB")
        if rgb.width != TILE_WIDTH:
            nh = max(1, int(rgb.height * TILE_WIDTH / rgb.width))
            rgb = rgb.resize((TILE_WIDTH, nh), Image.Resampling.LANCZOS)
        resized.append(rgb)

    if len(resized) == 1:
        return resized[0]

    out = resized[0]
    for nxt in resized[1:]:
        overlap = min(blend_px, out.height // 5, nxt.height // 5)
        if overlap < 6:
            canvas = Image.new("RGB", (TILE_WIDTH, out.height + nxt.height))
            canvas.paste(out, (0, 0))
            canvas.paste(nxt, (0, out.height))
            out = canvas
            continue

        keep_top = out.crop((0, 0, TILE_WIDTH, out.height - overlap))
        strip_a = out.crop((0, out.height - overlap, TILE_WIDTH, out.height))
        strip_b = nxt.crop((0, 0, TILE_WIDTH, overlap))
        strip_rest = nxt.crop((0, overlap, TILE_WIDTH, nxt.height))

        blended = Image.new("RGB", (TILE_WIDTH, overlap))
        pa = strip_a.load()
        pb = strip_b.load()
        pbld = blended.load()
        for y in range(overlap):
            t = y / max(overlap - 1, 1)
            for x in range(TILE_WIDTH):
                r1, g1, b1 = pa[x, y]
                r2, g2, b2 = pb[x, y]
                pbld[x, y] = (
                    int(r1 * (1 - t) + r2 * t),
                    int(g1 * (1 - t) + g2 * t),
                    int(b1 * (1 - t) + b2 * t),
                )

        total_h = keep_top.height + overlap + strip_rest.height
        canvas = Image.new("RGB", (TILE_WIDTH, total_h))
        canvas.paste(keep_top, (0, 0))
        canvas.paste(blended, (0, keep_top.height))
        canvas.paste(strip_rest, (0, keep_top.height + overlap))
        out = canvas

    return out


def build_strip_assets(
    plan: dict[str, Any],
    image_cfg: ImageConfig | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """生成连续底图长卷。"""
    from pipeline.strip import tile_generation_prompt

    client = get_image_client(image_cfg)
    if client is None:
        raise RuntimeError("未配置图像 API（IMAGE_API_KEY / OPENAI_API_KEY）")

    meta: dict[str, Any] = {"stages": ["parse_strip"], "tiles": []}
    style = plan["visual_style"]
    tile_images: list[Image.Image] = []
    tile_previews: list[dict[str, Any]] = []
    prev_seam: str | None = None

    for tile in plan["background_tiles"]:
        idx = tile["index"]
        meta["stages"].append(f"tile_{idx}_generate")
        prompt = tile_generation_prompt(tile, style, prev_seam)
        result = client.generate(prompt, size=BG_SIZE)
        raw = _image_bytes_from_api_result(result)
        img = Image.open(io.BytesIO(raw)).convert("RGB")

        weight = float(tile.get("height_weight") or 1.0)
        if abs(weight - 1.0) > 0.05:
            nh = max(1, int(img.height * weight))
            img = img.resize((img.width, nh), Image.Resampling.LANCZOS)

        tile_images.append(img)
        thumb = io.BytesIO()
        img.copy().resize((320, max(1, int(320 * img.height / img.width))), Image.Resampling.LANCZOS).save(
            thumb, format="JPEG", quality=80
        )
        tile_previews.append(
            {
                "index": idx,
                "scene": tile.get("scene", ""),
                "seam_bottom": tile.get("seam_bottom", ""),
                "preview": _to_data_uri(thumb.getvalue(), "image/jpeg"),
            }
        )
        meta["tiles"].append({"index": idx, "scene": tile.get("scene"), "height": img.height})
        prev_seam = tile.get("seam_bottom") or tile.get("scene")
        meta["stages"].append(f"tile_{idx}_done")

    meta["stages"].append("stitch_strip")
    strip_img = stitch_tiles_vertical(tile_images)
    strip_buf = io.BytesIO()
    strip_img.save(strip_buf, format="JPEG", quality=86)
    strip_jpeg = strip_buf.getvalue()
    strip_height = strip_img.height

    tile_heights = [img.height for img in tile_images]
    tile_offsets = compute_strip_tile_offsets(tile_heights)

    from pipeline.strip import sprite_generation_prompt

    sprite_layers: list[dict[str, Any]] = []
    character_anchor = plan.get("character_anchor") or ""
    for sprite in plan.get("sprites") or []:
        sid = sprite["id"]
        meta["stages"].append(f"sprite_{sid}_generate")
        sp_prompt = sprite_generation_prompt(sprite, character_anchor)
        sp_result = client.generate(sp_prompt, size=SUBJECT_SIZE)
        sp_raw = _image_bytes_from_api_result(sp_result)
        sp_png, cutout_method = _remove_background(sp_raw)
        meta.setdefault("sprites_meta", []).append({"id": sid, "cutout": cutout_method})

        sp_img = Image.open(io.BytesIO(sp_png))
        sp_w, sp_h = sp_img.size

        meta["stages"].append(f"sprite_{sid}_cutout")
        show_text = sprite.get("show_text", False)
        if show_text:
            text_png = render_text_png(
                sprite.get("text_content", ""),
                sprite.get("text_style", ""),
                sprite.get("text_position", "top"),
                sprite.get("text_role", "narration"),
            )
        else:
            text_png = render_text_png("", "", "top", "none")

        anchor_px = anchor_y_on_strip(
            tile_offsets,
            tile_heights,
            sprite["anchor_tile"],
            sprite["anchor_y"],
        )
        anchor_y_norm = anchor_px / strip_height if strip_height else 0.5

        thumb = io.BytesIO()
        sp_img.copy().resize(
            (120, max(1, int(120 * sp_h / max(sp_w, 1)))),
            Image.Resampling.LANCZOS,
        ).save(thumb, format="PNG")

        sprite_layers.append(
            {
                "id": sid,
                "label": sprite.get("label", ""),
                "b64": _to_b64(sp_png),
                "mime": "image/png",
                "data_uri": _to_data_uri(sp_png, "image/png"),
                "preview": _to_data_uri(thumb.getvalue(), "image/png"),
                "width": sp_w,
                "height": sp_h,
                "anchor_y_norm": round(anchor_y_norm, 5),
                "anchor_x": sprite.get("anchor_x", 0.5),
                "scale": sprite.get("scale", 0.32),
                "parallax": sprite.get("parallax", "scroll_follow"),
                "scroll_start": sprite.get("scroll_start", 0.0),
                "scroll_end": sprite.get("scroll_end", 1.0),
                "z_index": sprite.get("z_index", 10 + sid),
                "has_text": show_text,
                "text_b64": _to_b64(text_png),
                "text_mime": "image/png",
                "text_position": sprite.get("text_position", "top"),
                "text_reveal": sprite.get("text_reveal", "late"),
                "text_role": sprite.get("text_role", "none"),
            }
        )
        meta["stages"].append(f"sprite_{sid}_done")

    meta["stages"].append("encode_strip")
    assets = {
        "strip_b64": _to_b64(strip_jpeg),
        "strip_mime": "image/jpeg",
        "strip_data_uri": _to_data_uri(strip_jpeg, "image/jpeg"),
        "strip_width": strip_img.width,
        "strip_height": strip_height,
        "tile_count": len(tile_images),
        "tile_previews": tile_previews,
        "sprites": sprite_layers,
        "sprite_count": len(sprite_layers),
    }
    return assets, meta
