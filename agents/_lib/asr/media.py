"""媒体分类与可选抽音轨。不对 LS 暴露上传接口。"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".wma"}


def classify_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in _VIDEO_EXT:
        if path.endswith(ext):
            return "video"
    for ext in _AUDIO_EXT:
        if path.endswith(ext):
            return "audio"
    return "unknown"


def extract_audio_track(url: str, dest_wav: Path, *, timeout: int = 120) -> Path | None:
    """
    若本机有 ffmpeg，把音视频 URL 抽成 wav。
    Paraformer 仍打原始公网 URL（阿里云可拉视频）；抽轨结果供本地核对 / 时长兜底。
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.info("ffmpeg not found; skip local audio extract")
        return None
    dest_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        url,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(dest_wav),
    ]
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=timeout,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("ffmpeg extract failed: %s", exc)
        return None
    if dest_wav.is_file() and dest_wav.stat().st_size > 0:
        return dest_wav
    return None
