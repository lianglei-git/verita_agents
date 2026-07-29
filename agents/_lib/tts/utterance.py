"""Collect a single utterance into WAV bytes (provider-agnostic helper)."""

from __future__ import annotations

import base64
import logging
from typing import Any
from urllib.request import Request, urlopen

from _lib.tts.base import TtsError
from _lib.tts.types import TtsChunk
from _lib.tts.wav_utils import is_riff_wav, normalize_wav, pcm16le_to_wav, wav_duration_ms

logger = logging.getLogger(__name__)


def download_bytes(url: str, *, timeout: float = 60.0) -> bytes:
    req = Request(url, headers={"User-Agent": "verita-tts/1.0"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — TTS CDN URLs
        return resp.read()


def utterance_from_stream_chunks(
    chunks: list[TtsChunk],
    *,
    sample_rate: int = 24000,
) -> dict[str, Any]:
    """
    Build one utterance from stream events.
    Prefer final audio_url (full WAV); else concatenate PCM deltas into WAV.
    """
    pcm_parts: list[bytes] = []
    audio_url: str | None = None
    err: str | None = None

    for ch in chunks:
        if ch.event == "error":
            err = ch.error or "tts_error"
            break
        if ch.event == "audio_delta" and ch.audio_b64:
            pcm_parts.append(base64.b64decode(ch.audio_b64))
        if ch.event == "sentence_end" and ch.audio_url:
            audio_url = ch.audio_url
        if ch.sample_rate:
            sample_rate = ch.sample_rate

    if err:
        raise TtsError(err)

    wav_bytes: bytes | None = None
    if audio_url:
        try:
            raw = download_bytes(audio_url)
            if is_riff_wav(raw):
                wav_bytes = normalize_wav(raw)
            else:
                # Some CDNs may return raw pcm; wrap it
                wav_bytes = pcm16le_to_wav(raw, sample_rate=sample_rate)
        except Exception as exc:  # noqa: BLE001
            logger.warning("download audio_url failed, fallback to pcm: %s", exc)

    if wav_bytes is None:
        if not pcm_parts:
            raise TtsError("empty_audio_stream")
        pcm = b"".join(pcm_parts)
        if is_riff_wav(pcm):
            # Stream deltas may be one WAV or RIFF+extra; normalize to real PCM length
            wav_bytes = normalize_wav(pcm)
        else:
            wav_bytes = pcm16le_to_wav(pcm, sample_rate=sample_rate)

    duration_ms = wav_duration_ms(wav_bytes)
    return {
        "audio_bytes": wav_bytes,
        "mime": "audio/wav",
        "duration_ms": duration_ms,
        "sample_rate": sample_rate,
        "audio_url": audio_url,
    }


def synthesize_utterance(provider: Any, text: str, *, voice: str | None = None) -> dict[str, Any]:
    """Drain provider.synthesize_stream for one sentence → WAV bytes + duration."""
    events = list(
        provider.synthesize_stream(text, voice=voice, sentence_index=0)
    )
    sample_rate = getattr(getattr(provider, "cfg", None), "sample_rate", 24000) or 24000
    return utterance_from_stream_chunks(events, sample_rate=sample_rate)
