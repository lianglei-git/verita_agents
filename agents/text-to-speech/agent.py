"""text-to-speech — 流式试听 + 整段资料（单音频 + 句级字幕）。"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Iterator

_AGENT_DIR = Path(__file__).resolve().parent
_AGENTS_ROOT = _AGENT_DIR.parent
for path in (_AGENTS_ROOT, _AGENT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from _lib.tts import (  # noqa: E402
    TtsChunk,
    TtsConfig,
    TtsError,
    concat_wavs,
    get_provider,
    is_tts_available,
    synthesize_utterance,
)
from _lib.binary import BinaryError, put_bytes  # noqa: E402

AGENT_ID = "text-to-speech"
PACKAGE_VERSION = "1.2.0"
SKILL = "tts.speak"

# 仅按句号 / 问号 / 叹号 / 省略号拆分（保留标点在句末；不再按换行拆）
_SENTENCE_END_RE = re.compile(
    r"(?:……|…|\.{3,}|。{3,}|[。！？!?．]|\.(?=\s|$))\s*"
)

_REPO_ROOT = _AGENTS_ROOT.parent
_DEFAULT_MEDIA = _REPO_ROOT / "views" / "backend" / "media" / "tts"


def split_sentences(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(raw):
        piece = raw[start : match.end()].strip()
        if piece:
            sentences.append(piece)
        start = match.end()
    tail = raw[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def resolve_media_root(cfg: TtsConfig | None = None) -> Path:
    cfg = cfg or TtsConfig()
    raw = (cfg.media_dir or os.getenv("TTS_MEDIA_DIR", "")).strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_MEDIA.resolve()


def _history_safe_result(
    text: str,
    sentences_meta: list[dict[str, Any]],
    *,
    provider_name: str,
    model: str,
    voice: str,
    error: str | None = None,
    mode: str = "stream",
) -> dict[str, Any]:
    total = sum(int(s.get("duration_ms") or 0) for s in sentences_meta)
    out: dict[str, Any] = {
        "output": (
            f"合成 {len(sentences_meta)} 句"
            + (f" / 总时长 {total}ms" if total else "")
            + (f" · error={error}" if error else "")
        ),
        "mode": mode,
        "text": text,
        "sentences": [
            {
                "index": s["index"],
                "text": s["text"],
                "duration_ms": s.get("duration_ms"),
            }
            for s in sentences_meta
        ],
        "meta": {
            "agent": AGENT_ID,
            "package_version": PACKAGE_VERSION,
            "provider": provider_name,
            "model": model,
            "voice": voice,
            "ephemeral_audio": True,
            "sentence_count": len(sentences_meta),
            "total_duration_ms": total or None,
        },
    }
    if error:
        out["error"] = error
    return out


def _build_cfg(**kwargs: Any) -> TtsConfig:
    overrides: dict[str, Any] = {}
    for key in ("voice", "model", "provider", "media_dir"):
        if kwargs.get(key) is not None:
            overrides[key] = kwargs[key]
    return TtsConfig.from_overrides(overrides)


def iter_synthesis_events(
    user_input: str,
    **kwargs: Any,
) -> Iterator[dict[str, Any]]:
    """SSE events for stream preview mode."""
    text = (user_input or "").strip()
    if not text and isinstance(kwargs.get("text"), str):
        text = kwargs["text"].strip()

    cfg = _build_cfg(**kwargs)
    sentences = split_sentences(text)
    if not sentences:
        yield TtsChunk(event="error", error="empty_input").to_dict()
        yield TtsChunk(event="done").to_dict()
        return

    try:
        provider = get_provider(cfg)
    except TtsError as exc:
        yield TtsChunk(event="error", error=str(exc)).to_dict()
        yield TtsChunk(event="done").to_dict()
        return

    if not provider.is_available():
        err = (
            "tencent_tts_not_implemented"
            if getattr(provider, "name", "") == "tencent"
            else "tts_unavailable"
        )
        yield TtsChunk(event="error", error=err).to_dict()
        yield TtsChunk(event="done").to_dict()
        return

    for idx, sentence in enumerate(sentences):
        yield TtsChunk(
            event="sentence_start",
            sentence_index=idx,
            text=sentence,
        ).to_dict()

        for chunk in provider.synthesize_stream(
            sentence,
            voice=cfg.voice,
            sentence_index=idx,
        ):
            yield chunk.to_dict()
            if chunk.event == "error":
                yield TtsChunk(event="done").to_dict()
                return

    yield TtsChunk(event="done").to_dict()


def run_full(user_input: str, **kwargs: Any) -> dict[str, Any]:
    """
    Long-form teaching asset: split → per-sentence TTS → concat WAV → disk + subtitles.
    """
    text = (user_input or "").strip()
    cfg = _build_cfg(**kwargs)
    sentences = split_sentences(text)
    sentences_meta = [{"index": i, "text": s, "duration_ms": None} for i, s in enumerate(sentences)]

    try:
        provider = get_provider(cfg)
        pname = getattr(provider, "name", cfg.provider)
    except TtsError as exc:
        return _history_safe_result(
            text,
            sentences_meta,
            provider_name=cfg.provider,
            model=cfg.model,
            voice=cfg.voice,
            error=str(exc),
            mode="full",
        )

    if not sentences:
        return _history_safe_result(
            text,
            [],
            provider_name=pname,
            model=cfg.model,
            voice=cfg.voice,
            error="empty_input",
            mode="full",
        )

    if not is_tts_available(cfg):
        err = (
            "tencent_tts_not_implemented"
            if pname == "tencent"
            else "tts_unavailable"
        )
        return _history_safe_result(
            text,
            sentences_meta,
            provider_name=pname,
            model=cfg.model,
            voice=cfg.voice,
            error=err,
            mode="full",
        )

    job_id = uuid.uuid4().hex[:12]
    media_root = resolve_media_root(cfg)
    job_dir = media_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    wav_parts: list[bytes] = []
    subtitles: list[dict[str, Any]] = []
    cursor_ms = 0

    try:
        for idx, sentence in enumerate(sentences):
            utt = synthesize_utterance(provider, sentence, voice=cfg.voice)
            duration_ms = int(utt["duration_ms"] or 0)
            wav_parts.append(utt["audio_bytes"])
            sentences_meta[idx]["duration_ms"] = duration_ms
            subtitles.append(
                {
                    "index": idx,
                    "text": sentence,
                    "start_ms": cursor_ms,
                    "end_ms": cursor_ms + duration_ms,
                }
            )
            cursor_ms += duration_ms

        audio_bytes = concat_wavs(wav_parts)
        audio_path = job_dir / "audio.wav"
        audio_path.write_bytes(audio_bytes)

        subs_path = job_dir / "subtitles.json"
        subs_path.write_text(
            json.dumps(subtitles, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Relative path from media root for URL mounting: /media/tts/<job_id>/audio.wav
        rel_audio = f"{job_id}/audio.wav"
        rel_subs = f"{job_id}/subtitles.json"

        return {
            "output": f"full audio ready · {len(sentences)} sentences · {cursor_ms}ms",
            "mode": "full",
            "text": text,
            "audio": {
                "path": str(audio_path),
                "relative_path": rel_audio,
                "url": f"/media/tts/{rel_audio}",
                "mime": "audio/wav",
                "duration_ms": cursor_ms,
            },
            "subtitles": subtitles,
            "subtitles_path": str(subs_path),
            "subtitles_url": f"/media/tts/{rel_subs}",
            "sentences": [
                {
                    "index": s["index"],
                    "text": s["text"],
                    "duration_ms": s.get("duration_ms"),
                }
                for s in sentences_meta
            ],
            "meta": {
                "agent": AGENT_ID,
                "package_version": PACKAGE_VERSION,
                "provider": pname,
                "model": cfg.model,
                "voice": cfg.voice,
                "job_id": job_id,
                "ephemeral_audio": False,
                "sentence_count": len(sentences),
                "total_duration_ms": cursor_ms,
                "media_root": str(media_root),
            },
        }
    except Exception as exc:  # noqa: BLE001
        return _history_safe_result(
            text,
            sentences_meta,
            provider_name=pname,
            model=cfg.model,
            voice=cfg.voice,
            error=str(exc),
            mode="full",
        )


def _synthesize_wav(text: str, cfg: TtsConfig) -> dict[str, Any]:
    sentences = split_sentences(text)
    if not sentences:
        raise TtsError("empty_input")
    provider = get_provider(cfg)
    if not is_tts_available(cfg):
        raise TtsError("tts_unavailable")
    wav_parts: list[bytes] = []
    cursor_ms = 0
    for sentence in sentences:
        utt = synthesize_utterance(provider, sentence, voice=cfg.voice)
        wav_parts.append(utt["audio_bytes"])
        cursor_ms += int(utt["duration_ms"] or 0)
    return {
        "wav": concat_wavs(wav_parts),
        "duration_ms": cursor_ms,
        "sentence_count": len(sentences),
        "provider": getattr(provider, "name", cfg.provider),
    }


def run_speak(user_input: str, **kwargs: Any) -> dict[str, Any]:
    """LS tts.speak：合成 WAV，有 upload 则预签 PUT，output 只回元数据。"""
    text = str(kwargs.get("text") or user_input or "").strip()
    language = str(kwargs.get("language") or "").strip() or None
    cfg = _build_cfg(**kwargs)
    meta = {
        "agent": AGENT_ID,
        "package_version": PACKAGE_VERSION,
        "skill": SKILL,
        "language": language,
        "voice": cfg.voice,
        "model": cfg.model,
    }
    if not text:
        return {"error": "empty_input", "message": "provide text", "output": None, "meta": meta}
    if not is_tts_available(cfg):
        return {
            "error": "tts_unavailable",
            "message": "TTS 未配置或已禁用",
            "output": None,
            "meta": meta,
        }
    try:
        synth = _synthesize_wav(text, cfg)
        wav = synth["wav"]
    except TtsError as exc:
        return {"error": str(exc) or "tts_failed", "message": str(exc), "output": None, "meta": meta}
    except Exception as exc:  # noqa: BLE001
        return {"error": "tts_failed", "message": str(exc), "output": None, "meta": meta}

    duration_sec = round(synth["duration_ms"] / 1000.0, 3)
    mime = "audio/wav"
    filename = "tts.wav"
    upload = kwargs.get("upload")
    ls_mode = isinstance(upload, dict)
    if ls_mode:
        try:
            put_bytes(upload, wav, default_content_type=mime)
        except BinaryError as exc:
            return {"error": exc.code, "message": exc.message, "output": None, "meta": meta}

    preview = None
    if not ls_mode:
        job_id = uuid.uuid4().hex[:12]
        job_dir = resolve_media_root(cfg) / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        path = job_dir / filename
        path.write_bytes(wav)
        preview = {"url": f"/media/tts/{job_id}/{filename}", "path": str(path)}
    return {
        "output": {
            "uploaded": bool(ls_mode),
            "bytes": len(wav),
            "mime": mime,
            "filename": filename,
            "duration_sec": duration_sec,
        },
        "preview": preview,
        "usage": {
            "provider": synth["provider"],
            "model": cfg.model,
            "tokens": 0,
            "usage_sec": duration_sec,
            "cost_micros": None,
        },
        "meta": {**meta, "sentence_count": synth["sentence_count"]},
    }


def run(user_input: str, **kwargs: Any) -> dict[str, Any]:
    """
    upload 或 mode=speak 或 LS 扁平 text 字段 → tts.speak。
    mode=full → 工作台整段资料。
    otherwise → 工作台轻量摘要（试听走 /stream）。
    """
    mode = str(kwargs.get("mode") or "").strip().lower()
    if (
        isinstance(kwargs.get("upload"), dict)
        or mode == "speak"
        or ("text" in kwargs and mode not in {"stream", "full", "asset", "material"})
    ):
        return run_speak(user_input, **kwargs)
    if mode in {"full", "asset", "material"}:
        return run_full(user_input, **kwargs)

    text = (user_input or "").strip()
    cfg = _build_cfg(**kwargs)
    sentences = split_sentences(text)
    sentences_meta = [{"index": i, "text": s, "duration_ms": None} for i, s in enumerate(sentences)]

    try:
        provider = get_provider(cfg)
        pname = getattr(provider, "name", cfg.provider)
    except TtsError as exc:
        return _history_safe_result(
            text,
            sentences_meta,
            provider_name=cfg.provider,
            model=cfg.model,
            voice=cfg.voice,
            error=str(exc),
        )

    if not sentences:
        return _history_safe_result(
            text,
            [],
            provider_name=pname,
            model=cfg.model,
            voice=cfg.voice,
            error="empty_input",
        )

    if not is_tts_available(cfg):
        return _history_safe_result(
            text,
            sentences_meta,
            provider_name=pname,
            model=cfg.model,
            voice=cfg.voice,
            error="tts_unavailable",
        )

    return _history_safe_result(
        text,
        sentences_meta,
        provider_name=pname,
        model=cfg.model,
        voice=cfg.voice,
    )


def strip_audio_from_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """History-safe copy: drop binary payloads; keep paths/urls for full mode."""
    if not isinstance(result, dict):
        return result
    import copy

    slim = copy.deepcopy(result)
    for key in ("audio_b64", "audio_data_uri", "audio_url"):
        slim.pop(key, None)

    audio = slim.get("audio")
    if isinstance(audio, dict):
        slim["audio"] = {
            k: v
            for k, v in audio.items()
            if k not in {"audio_b64", "data", "bytes", "audio_bytes"}
        }
    elif "audio" in slim and not isinstance(audio, dict):
        # legacy blob — drop
        slim.pop("audio", None)

    sentences = slim.get("sentences")
    if isinstance(sentences, list):
        cleaned = []
        for item in sentences:
            if not isinstance(item, dict):
                cleaned.append(item)
                continue
            row = {
                k: v
                for k, v in item.items()
                if k not in {"audio_b64", "audio_data_uri", "audio_url", "audio", "data"}
            }
            cleaned.append(row)
        slim["sentences"] = cleaned

    meta = slim.get("meta")
    if isinstance(meta, dict) and meta.get("ephemeral_audio") is not False:
        meta["ephemeral_audio"] = True
    return slim


if __name__ == "__main__":
    sample = sys.argv[1] if len(sys.argv) > 1 else "你好。这是第二句。"
    mode = "full" if "--full" in sys.argv else "stream"
    print(json.dumps(run(sample, mode=mode), ensure_ascii=False, indent=2))
