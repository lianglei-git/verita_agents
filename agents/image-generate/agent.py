"""image.generate — 一个 skill + mode，风格锚锁死，产物 PNG 走预签 PUT。"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parent
_AGENTS_ROOT = _AGENT_DIR.parent
for path in (_AGENTS_ROOT, _AGENT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from _lib.binary import BinaryError, put_bytes  # noqa: E402
from _lib.image import get_image_client, is_image_api_available  # noqa: E402
from _lib.image.png import ensure_png, fetch_image_bytes, png_size  # noqa: E402

from handbook import (  # noqa: E402
    MODE_SPEC,
    MODES,
    STYLE_VERSION,
    cover_prompt,
    goal_prompt_from_motif,
    goal_prompt_from_scenes,
    sentence_prompt,
    spot_prompt,
    translate_goal_scenes,
    visual_from_lemma,
    vocabulary_prompt,
)

AGENT_ID = "image-generate"
PACKAGE_VERSION = "1.0.0"
SKILL = "image.generate"
_REPO_ROOT = _AGENTS_ROOT.parent
_DEFAULT_MEDIA = _REPO_ROOT / "views" / "backend" / "media" / "images"


def _media_root() -> Path:
    raw = os.getenv("IMAGE_MEDIA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_MEDIA.resolve()


def resolve_mode(kwargs: dict[str, Any]) -> str:
    raw = str(kwargs.get("mode") or kwargs.get("input_mode") or "cover").strip().lower()
    aliases = {
        "collection": "cover",
        "collection_cover": "cover",
        "illustration": "spot",
        "function": "spot",
        "ui": "spot",
        "vocab": "vocabulary",
        "word": "vocabulary",
        "goal_illustration": "goal",
    }
    mode = aliases.get(raw, raw)
    if mode not in MODES:
        raise ValueError(mode)
    return mode


def build_prompt(mode: str, kwargs: dict[str, Any], user_input: str) -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {"mode": mode, "style_version": STYLE_VERSION}
    subject = str(kwargs.get("subject") or user_input or "").strip()

    if mode == "cover":
        composition = str(kwargs.get("composition") or "centered").strip().lower()
        if composition not in {"centered", "thirds", "panorama"}:
            composition = "centered"
        if not subject:
            raise ValueError("empty_subject")
        meta["composition"] = composition
        return cover_prompt(subject, composition), meta

    if mode == "goal":
        profile = kwargs.get("profile") if isinstance(kwargs.get("profile"), dict) else None
        goal_text = str((profile or {}).get("goal") or "").strip()
        identity = str((profile or {}).get("identity") or "").strip()
        current = str((profile or {}).get("current") or "").strip()
        if profile and len(goal_text) >= 10 and identity and current:
            scenes = translate_goal_scenes(profile)
            if scenes:
                meta["track"] = "b"
                return goal_prompt_from_scenes(**scenes), meta
        motif = str(kwargs.get("motif") or "mountain_path").strip().lower()
        meta["track"] = "a"
        meta["motif"] = motif if motif in {
            "mountain_path", "skyline", "book_steps", "bridge",
            "harbor", "doorway", "runway", "compass",
        } else "mountain_path"
        return goal_prompt_from_motif(meta["motif"]), meta

    if mode == "spot":
        kind = str(kwargs.get("kind") or "empty").strip().lower()
        if kind not in {"empty", "onboarding", "badge", "error"}:
            kind = "empty"
        meta["kind"] = kind
        return spot_prompt(subject, kind), meta

    if mode == "vocabulary":
        visual = str(kwargs.get("visual") or "").strip()
        lemma = str(kwargs.get("lemma") or subject).strip()
        pos = str(kwargs.get("pos") or "noun").strip().lower()
        sense = str(kwargs.get("sense") or "").strip()
        if not visual:
            if not lemma:
                raise ValueError("empty_subject")
            visual = visual_from_lemma(lemma, pos, sense)
        meta["lemma"] = lemma
        meta["pos"] = pos
        return vocabulary_prompt(visual), meta

    text = str(kwargs.get("text") or subject).strip()
    if not text:
        raise ValueError("empty_subject")
    return sentence_prompt(text), meta


def _fail(code: str, message: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": code,
        "message": message,
        "output": extra.pop("output", None),
        "meta": {"agent": AGENT_ID, "package_version": PACKAGE_VERSION, "skill": SKILL},
    }
    body.update(extra)
    return body


def run(user_input: str = "", **kwargs: Any) -> dict[str, Any]:
    try:
        mode = resolve_mode(kwargs)
    except ValueError as exc:
        return _fail("invalid_mode", f"mode must be one of {', '.join(MODES)}", requested=str(exc))

    spec = MODE_SPEC[mode]
    try:
        prompt, prompt_meta = build_prompt(mode, kwargs, user_input)
    except ValueError:
        return _fail("empty_subject", "provide subject / lemma / text for this mode")

    upload = kwargs.get("upload")
    ls_mode = isinstance(upload, dict)

    if not is_image_api_available():
        return _fail("image_unavailable", "IMAGE_API_KEY / OPENAI_API_KEY not configured")

    client = get_image_client()
    if client is None:
        return _fail("image_unavailable", "image client missing")

    try:
        raw = client.generate(prompt, size=spec["size"])
        png = ensure_png(fetch_image_bytes(raw))
        width, height = png_size(png)
    except Exception as exc:  # noqa: BLE001
        return _fail("image_failed", str(exc))

    filename = spec["filename"]
    mime = "image/png"
    if ls_mode:
        max_bytes = 0
        try:
            max_bytes = int((upload or {}).get("max_bytes") or 0)
        except (TypeError, ValueError):
            max_bytes = 0
        if max_bytes and len(png) > max_bytes:
            return _fail("payload_too_large", f"{len(png)} exceeds max_bytes")
        try:
            put_bytes(upload, png, default_content_type=mime)
        except BinaryError as exc:
            return _fail(exc.code, exc.message)

    preview = None
    if not ls_mode:
        job_id = uuid.uuid4().hex[:12]
        dest = _media_root() / job_id
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / filename
        path.write_bytes(png)
        preview = {
            "url": f"/media/images/{job_id}/{filename}",
            "path": str(path),
        }

    output = {
        "uploaded": bool(ls_mode),
        "bytes": len(png),
        "mime": mime,
        "filename": filename,
        "width": width,
        "height": height,
    }
    return {
        "output": output,
        "preview": preview,
        "usage": {
            "provider": "image",
            "model": getattr(getattr(client, "cfg", None), "model", "") or "",
            "tokens": 1,
            "usage_sec": 0,
            "cost_micros": None,
        },
        "meta": {
            "agent": AGENT_ID,
            "package_version": PACKAGE_VERSION,
            "skill": SKILL,
            "prompt": prompt,
            **prompt_meta,
        },
    }


if __name__ == "__main__":
    sample = {
        "mode": "spot",
        "kind": "empty",
        "subject": "An open empty book with a small violet bookmark ribbon",
    }
    print(json.dumps(run("", **sample), ensure_ascii=False, indent=2))
