"""speech-to-text — 跟读校对（qwen3-asr-flash）+ 字幕（Paraformer）。"""

from __future__ import annotations

import base64
import json
import mimetypes
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

from _lib.asr import (  # noqa: E402
    AsrConfig,
    AsrError,
    classify_url,
    diff_tokens,
    extract_audio_track,
    is_asr_available,
    to_transcribe_output,
    transcribe_audio,
    transcribe_url,
)

AGENT_ID = "speech-to-text"
PACKAGE_VERSION = "1.2.0"
SKILL = "asr.transcribe"

_REPO_ROOT = _AGENTS_ROOT.parent
_DEFAULT_MEDIA = _REPO_ROOT / "views" / "backend" / "media" / "asr"

_MIME_EXT = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
}


def resolve_media_root(cfg: AsrConfig | None = None) -> Path:
    cfg = cfg or AsrConfig()
    raw = (cfg.media_dir or os.getenv("ASR_MEDIA_DIR", "")).strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_MEDIA.resolve()


def _build_cfg(**kwargs: Any) -> AsrConfig:
    overrides: dict[str, Any] = {}
    for key in (
        "model",
        "subtitle_model",
        "compare_model",
        "media_dir",
        "api_key",
        "base_http_api_url",
        "compatible_base_url",
    ):
        if kwargs.get(key) is not None:
            overrides[key] = kwargs[key]
    return AsrConfig.from_overrides(overrides)


def _ext_for_mime(mime: str) -> str:
    mime = (mime or "").split(";")[0].strip().lower()
    if mime in _MIME_EXT:
        return _MIME_EXT[mime]
    guessed = mimetypes.guess_extension(mime or "") or ".wav"
    return guessed


def _save_audio_bytes(data: bytes, *, mime: str, cfg: AsrConfig) -> tuple[str, Path, str]:
    job_id = uuid.uuid4().hex[:12]
    root = resolve_media_root(cfg)
    job_dir = root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    ext = _ext_for_mime(mime)
    path = job_dir / f"audio{ext}"
    path.write_bytes(data)
    rel = f"{job_id}/audio{ext}"
    return job_id, path, rel


def _decode_base64_audio(raw: str, default_mime: str) -> tuple[bytes, str]:
    mime = default_mime
    payload = raw.strip()
    if payload.startswith("data:"):
        header, _, payload = payload.partition(",")
        if ";base64" in header and header.startswith("data:"):
            mime = header[5:].split(";")[0] or mime
    return base64.b64decode(payload), mime


def _load_local_audio(kwargs: Any, cfg: AsrConfig) -> tuple[str, Path, str, bytes, str]:
    """Save uploaded/local audio; returns job_id, path, rel, bytes, mime."""
    audio_path = kwargs.get("audio_path") or kwargs.get("path")
    if isinstance(audio_path, str) and audio_path.strip():
        p = Path(audio_path.strip()).expanduser()
        if not p.is_file():
            raise AsrError(f"audio_file_not_found: {p}")
        data = p.read_bytes()
        mime = str(kwargs.get("audio_mime") or mimetypes.guess_type(str(p))[0] or "audio/wav")
        job_id, saved, rel = _save_audio_bytes(data, mime=mime, cfg=cfg)
        return job_id, saved, rel, data, mime

    b64 = kwargs.get("audio_base64") or kwargs.get("audio")
    if isinstance(b64, str) and b64.strip():
        mime = str(kwargs.get("audio_mime") or "audio/webm")
        data, mime = _decode_base64_audio(b64, mime)
        job_id, saved, rel = _save_audio_bytes(data, mime=mime, cfg=cfg)
        return job_id, saved, rel, data, mime

    raise AsrError("missing_audio: provide audio_base64, audio_path, or audio_url")


def _ingest_for_compare(kwargs: Any, cfg: AsrConfig) -> dict[str, Any]:
    """Compare uses qwen3-asr-flash: prefer base64 bytes; public URL optional."""
    audio_url = kwargs.get("audio_url")
    if isinstance(audio_url, str) and audio_url.strip().startswith(("http://", "https://")):
        return {
            "job_id": uuid.uuid4().hex[:12],
            "local_path": None,
            "rel": None,
            "audio_bytes": None,
            "mime": str(kwargs.get("audio_mime") or "audio/wav"),
            "audio_url": audio_url.strip(),
        }

    job_id, saved, rel, data, mime = _load_local_audio(kwargs, cfg)
    return {
        "job_id": job_id,
        "local_path": saved,
        "rel": rel,
        "audio_bytes": data,
        "mime": mime,
        "audio_url": None,
    }


def _require_public_audio_url(kwargs: Any, user_input: str = "") -> str:
    """Subtitle / Paraformer: caller must supply a publicly reachable http(s) URL."""
    candidates = [
        kwargs.get("audio_url"),
        kwargs.get("url"),
        user_input,
    ]
    for raw in candidates:
        if isinstance(raw, str) and raw.strip().startswith(("http://", "https://")):
            return raw.strip()
    raise AsrError(
        "missing_audio_url: subtitle mode requires a publicly reachable "
        "http(s) audio_url (Paraformer cannot use local/base64 upload)"
    )


def _meta(cfg: AsrConfig, job_id: str, *, provider: str, model: str, **extra: Any) -> dict[str, Any]:
    return {
        "agent": AGENT_ID,
        "package_version": PACKAGE_VERSION,
        "provider": provider,
        "model": model,
        "job_id": job_id,
        **extra,
    }


def run_compare(user_input: str, **kwargs: Any) -> dict[str, Any]:
    reference = (
        kwargs.get("reference")
        or kwargs.get("reference_text")
        or user_input
        or ""
    )
    reference = str(reference).strip()
    if not reference:
        return {
            "mode": "compare",
            "error": "missing_reference",
            "message": "跟读校对需要参考文本（reference）",
            "meta": {"agent": AGENT_ID},
        }

    cfg = _build_cfg(**kwargs)
    if not is_asr_available(cfg):
        return {
            "mode": "compare",
            "error": "asr_unavailable",
            "reference": reference,
            "meta": _meta(cfg, "", provider="qwen3-asr-flash", model=cfg.compare_model),
        }

    try:
        ingested = _ingest_for_compare(kwargs, cfg)
        result = transcribe_audio(
            audio_bytes=ingested["audio_bytes"],
            audio_url=ingested["audio_url"],
            mime=ingested["mime"],
            cfg=cfg,
        )
        diff, stats = diff_tokens(reference, result.transcript)
        out: dict[str, Any] = {
            "output": f"compare · accuracy={stats['accuracy']}",
            "mode": "compare",
            "transcript": result.transcript,
            "reference": reference,
            "diff": diff,
            "stats": stats,
            "subtitles": result.to_subtitles(),
            "meta": _meta(
                cfg,
                ingested["job_id"],
                provider="qwen3-asr-flash",
                model=cfg.compare_model,
            ),
        }
        if ingested["local_path"] is not None and ingested["rel"] is not None:
            out["audio"] = {
                "path": str(ingested["local_path"]),
                "relative_path": ingested["rel"],
                "url": f"/media/asr/{ingested['rel']}",
            }
        return out
    except AsrError as exc:
        return {
            "mode": "compare",
            "error": str(exc),
            "reference": reference,
            "meta": _meta(cfg, "", provider="qwen3-asr-flash", model=cfg.compare_model),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "mode": "compare",
            "error": str(exc),
            "reference": reference,
            "meta": _meta(cfg, "", provider="qwen3-asr-flash", model=cfg.compare_model),
        }


def _truthy(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def run_subtitle(user_input: str, **kwargs: Any) -> dict[str, Any]:
    cfg = _build_cfg(**kwargs)
    model = cfg.subtitle_model or cfg.model
    language = str(kwargs.get("language") or "").strip() or None
    enable_words = _truthy(kwargs.get("enable_word_timestamps"), True)
    provider_meta = _meta(cfg, "", provider="aliyun", model=model, skill=SKILL)
    if not is_asr_available(cfg):
        return {
            "mode": "subtitle",
            "error": "asr_unavailable",
            "message": "ASR 未配置或已禁用",
            "meta": provider_meta,
        }

    try:
        file_url = _require_public_audio_url(kwargs, user_input)
        job_id = uuid.uuid4().hex[:12]
        media_kind = classify_url(file_url)
        job_dir = resolve_media_root(cfg) / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        extracted = None
        if media_kind == "video":
            extracted = extract_audio_track(file_url, job_dir / "audio.wav")

        result = transcribe_url(file_url, cfg, language=language)
        output = to_transcribe_output(result, enable_word_timestamps=enable_words)
        subtitles = result.to_subtitles()
        subs_path = job_dir / "subtitles.json"
        subs_path.write_text(
            json.dumps(subtitles, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        usage_sec = output["duration_sec"]
        return {
            "output": output,
            "mode": "subtitle",
            "transcript": result.transcript,
            "subtitles": subtitles,
            "audio": {"url": file_url},
            "subtitles_path": str(subs_path),
            "subtitles_url": f"/media/asr/{job_id}/subtitles.json",
            "usage": {
                "provider": "aliyun",
                "model": model,
                "tokens": 0,
                "usage_sec": usage_sec,
            },
            "meta": _meta(
                cfg,
                job_id,
                provider="aliyun",
                model=model,
                skill=SKILL,
                file_url=file_url,
                language=language,
                media_kind=media_kind,
                extracted_audio=str(extracted) if extracted else None,
                usage_sec=usage_sec,
            ),
        }
    except AsrError as exc:
        return {
            "mode": "subtitle",
            "error": str(exc),
            "message": str(exc),
            "meta": provider_meta,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "mode": "subtitle",
            "error": str(exc),
            "message": str(exc),
            "meta": provider_meta,
        }


def _is_transcribe_request(mode: str, kwargs: Any) -> bool:
    if mode in {"subtitle", "subs", "captions", "transcribe", "asr"}:
        return True
    if mode in {"compare", "proofread"}:
        return False
    if kwargs.get("language"):
        return True
    audio_url = kwargs.get("audio_url") or kwargs.get("url")
    if isinstance(audio_url, str) and audio_url.startswith(("http://", "https://")):
        if not (kwargs.get("reference") or kwargs.get("reference_text")):
            return True
    return False


def run(user_input: str, **kwargs: Any) -> dict[str, Any]:
    mode = str(kwargs.get("mode") or "").strip().lower()
    if _is_transcribe_request(mode, kwargs):
        return run_subtitle(user_input, **kwargs)
    return run_compare(user_input, **kwargs)


if __name__ == "__main__":
    print(
        json.dumps(
            run("", mode="compare", reference="你好", audio_url="https://example.com/a.wav"),
            ensure_ascii=False,
            indent=2,
        )
    )
