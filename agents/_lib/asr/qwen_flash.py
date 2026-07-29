"""阿里云 qwen3-asr-flash（OpenAI 兼容，支持 base64 Data URI）。"""

from __future__ import annotations

import base64
import logging
from typing import Any

from _lib.asr.config import AsrConfig
from _lib.asr.errors import AsrError
from _lib.asr.types import AsrResult, AsrSentence

logger = logging.getLogger(__name__)

# Docs: Base64-encoded audio should stay under 10 MB.
_MAX_B64_CHARS = 10 * 1024 * 1024


def _data_uri(audio_bytes: bytes, mime: str) -> str:
    mime = (mime or "audio/wav").split(";")[0].strip() or "audio/wav"
    b64 = base64.b64encode(audio_bytes).decode("ascii")
    if len(b64) > _MAX_B64_CHARS:
        raise AsrError(
            f"audio_too_large_for_qwen_base64: base64={len(b64)} "
            f"limit={_MAX_B64_CHARS}"
        )
    return f"data:{mime};base64,{b64}"


def transcribe_audio(
    *,
    audio_bytes: bytes | None = None,
    audio_url: str | None = None,
    mime: str = "audio/wav",
    cfg: AsrConfig | None = None,
    language: str | None = None,
) -> AsrResult:
    """
    Recognize speech with qwen3-asr-flash.

    Prefer small local files via ``audio_bytes`` (sent as base64 Data URI).
    Public ``audio_url`` is also accepted.
    """
    cfg = cfg or AsrConfig()
    if cfg.disabled or not cfg.api_key:
        raise AsrError("asr_unavailable")

    data: str | None = None
    if audio_bytes is not None:
        if not audio_bytes:
            raise AsrError("empty_audio_bytes")
        data = _data_uri(audio_bytes, mime)
    elif audio_url and audio_url.strip().startswith(("http://", "https://")):
        data = audio_url.strip()
    else:
        raise AsrError("missing_audio_for_qwen: provide audio_bytes or audio_url")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AsrError("openai package not installed") from exc

    client = OpenAI(api_key=cfg.api_key, base_url=cfg.compatible_base_url)

    asr_options: dict[str, Any] = {"enable_itn": False}
    lang = (language or "").strip()
    if lang:
        asr_options["language"] = lang

    try:
        completion = client.chat.completions.create(
            model=cfg.compare_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": data},
                        }
                    ],
                }
            ],
            stream=False,
            extra_body={"asr_options": asr_options},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("qwen3-asr-flash failed")
        raise AsrError(str(exc)) from exc

    text = ""
    try:
        text = (completion.choices[0].message.content or "").strip()
    except (AttributeError, IndexError, TypeError):
        text = ""

    if not text:
        raise AsrError(f"qwen_asr_empty_result: {completion}")

    sentences = [AsrSentence(index=0, text=text)]
    raw: Any = None
    if hasattr(completion, "model_dump"):
        try:
            raw = completion.model_dump()
        except Exception:  # noqa: BLE001
            raw = str(completion)
    else:
        raw = str(completion)
    return AsrResult(transcript=text, sentences=sentences, raw=raw)
