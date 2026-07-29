"""WAV / PCM helpers for TTS full-mode stitching."""

from __future__ import annotations

import io
import wave
from typing import Iterable


def pcm16le_to_wav(pcm: bytes, *, sample_rate: int = 24000, channels: int = 1) -> bytes:
    """Wrap raw Int16 LE PCM into a mono/stereo WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _frame_size(channels: int, sampwidth: int) -> int:
    return max(1, channels * sampwidth)


def read_wav_pcm(wav_bytes: bytes) -> tuple[int, int, int, bytes]:
    """
    Return (channels, sampwidth, framerate, pcm_frames).
    Uses *actual* readable PCM length — DashScope/OSS WAVs sometimes declare
    a bogus huge data-chunk size; trusting getnframes() alone inflates duration.
    """
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels = wf.getnchannels() or 1
        sampwidth = wf.getsampwidth() or 2
        rate = wf.getframerate() or 24000
        # Read as much as the stream actually has (not the claimed nframes).
        claimed = wf.getnframes()
        pcm = wf.readframes(claimed if claimed > 0 else 10**12)
    fs = _frame_size(channels, sampwidth)
    # Truncate to whole frames
    n = (len(pcm) // fs) * fs
    return channels, sampwidth, rate, pcm[:n]


def normalize_wav(wav_bytes: bytes) -> bytes:
    """Re-encode WAV with a correct header from actual PCM payload."""
    channels, sampwidth, rate, pcm = read_wav_pcm(wav_bytes)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def wav_duration_ms(wav_bytes: bytes) -> int:
    channels, sampwidth, rate, pcm = read_wav_pcm(wav_bytes)
    fs = _frame_size(channels, sampwidth)
    actual_frames = len(pcm) // fs
    rate = rate or 1
    return int(round(actual_frames * 1000 / rate))


def read_wav_params(wav_bytes: bytes) -> tuple[int, int, int, bytes]:
    """Return (channels, sampwidth, framerate, frames_bytes) — actual PCM only."""
    return read_wav_pcm(wav_bytes)


def concat_wavs(parts: Iterable[bytes]) -> bytes:
    """Concatenate WAV blobs; normalize each part first so headers cannot lie."""
    chunks = [p for p in parts if p]
    if not chunks:
        raise ValueError("no wav parts to concatenate")

    normalized = [normalize_wav(c) for c in chunks]
    if len(normalized) == 1:
        return normalized[0]

    channels, sampwidth, rate, frames = read_wav_pcm(normalized[0])
    all_frames = [frames]
    for part in normalized[1:]:
        c, sw, r, fr = read_wav_pcm(part)
        if (c, sw, r) != (channels, sampwidth, rate):
            raise ValueError(
                f"wav param mismatch: expected {(channels, sampwidth, rate)}, got {(c, sw, r)}"
            )
        all_frames.append(fr)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(rate)
        for fr in all_frames:
            wf.writeframes(fr)
    return buf.getvalue()


def is_riff_wav(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
