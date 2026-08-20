"""WAV → MP3 for LS tts.speak (upload.headers Content-Type=audio/mpeg)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from _lib.tts.base import TtsError

logger = logging.getLogger(__name__)


def wav_to_mp3(wav_bytes: bytes) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise TtsError("ffmpeg_missing")
    with tempfile.TemporaryDirectory(prefix="tts-mp3-") as td:
        src = Path(td) / "in.wav"
        dst = Path(td) / "out.mp3"
        src.write_bytes(wav_bytes)
        for codec in ("libmp3lame", "mp3"):
            cmd = [ffmpeg, "-y", "-i", str(src), "-codec:a", codec, "-q:a", "4", str(dst)]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=60,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.warning("ffmpeg mp3 failed: %s", exc)
                continue
            if proc.returncode == 0 and dst.is_file() and dst.stat().st_size > 0:
                return dst.read_bytes()
        raise TtsError("mp3_encode_failed")
