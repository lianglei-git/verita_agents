"""阿里云百炼 DashScope Qwen-TTS 流式 provider。"""

from __future__ import annotations

import logging
from typing import Any, Iterator

from _lib.tts.base import TtsError
from _lib.tts.config import TtsConfig
from _lib.tts.types import TtsChunk

logger = logging.getLogger(__name__)


def _audio_from_chunk(chunk: Any) -> tuple[str | None, str | None]:
    """Return (data_b64, url) from a DashScope response-like object."""
    output = getattr(chunk, "output", None)
    if output is None and isinstance(chunk, dict):
        output = chunk.get("output")
    if output is None:
        return None, None

    audio = getattr(output, "audio", None)
    if audio is None and isinstance(output, dict):
        audio = output.get("audio")
    if audio is None:
        return None, None

    if isinstance(audio, dict):
        data = audio.get("data") or None
        url = audio.get("url") or None
    else:
        data = getattr(audio, "data", None) or None
        url = getattr(audio, "url", None) or None

    if isinstance(data, str) and not data.strip():
        data = None
    if isinstance(url, str) and not url.strip():
        url = None
    return data, url


def _status_code(chunk: Any) -> int | None:
    code = getattr(chunk, "status_code", None)
    if code is None and isinstance(chunk, dict):
        code = chunk.get("status_code")
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def _error_message(chunk: Any) -> str:
    msg = getattr(chunk, "message", None)
    code = getattr(chunk, "code", None)
    if isinstance(chunk, dict):
        msg = msg or chunk.get("message")
        code = code or chunk.get("code")
    parts = [p for p in (str(code or "").strip(), str(msg or "").strip()) if p]
    return " / ".join(parts) or "DashScope TTS failed"


class AliyunDashScopeProvider:
    name = "aliyun"

    def __init__(self, cfg: TtsConfig | None = None):
        self.cfg = cfg or TtsConfig()

    def is_available(self) -> bool:
        if self.cfg.disabled:
            return False
        return bool(self.cfg.dashscope_api_key)

    def synthesize_stream(
        self,
        text: str,
        *,
        voice: str | None = None,
        sentence_index: int = 0,
    ) -> Iterator[TtsChunk]:
        text = (text or "").strip()
        if not text:
            yield TtsChunk(
                event="error",
                sentence_index=sentence_index,
                error="empty_text",
            )
            return

        if not self.is_available():
            yield TtsChunk(
                event="error",
                sentence_index=sentence_index,
                text=text,
                error="tts_unavailable",
            )
            return

        try:
            import dashscope
        except ImportError as exc:
            raise TtsError(
                "dashscope package not installed; pip install 'dashscope>=1.24.5'"
            ) from exc

        dashscope.base_http_api_url = self.cfg.dashscope_base_url
        voice_name = (voice or self.cfg.voice or "Cherry").strip()
        mime = self.cfg.mime
        sample_rate = self.cfg.sample_rate

        try:
            response = dashscope.MultiModalConversation.call(
                model=self.cfg.model,
                api_key=self.cfg.dashscope_api_key,
                text=text,
                voice=voice_name,
                stream=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("DashScope TTS call failed")
            yield TtsChunk(
                event="error",
                sentence_index=sentence_index,
                text=text,
                error=str(exc),
            )
            return

        saw_delta = False
        final_url: str | None = None

        try:
            for chunk in response:
                status = _status_code(chunk)
                if status is not None and status != 200:
                    yield TtsChunk(
                        event="error",
                        sentence_index=sentence_index,
                        text=text,
                        error=_error_message(chunk),
                    )
                    return

                data_b64, url = _audio_from_chunk(chunk)
                if data_b64:
                    saw_delta = True
                    yield TtsChunk(
                        event="audio_delta",
                        sentence_index=sentence_index,
                        text=text,
                        audio_b64=data_b64,
                        mime=mime,
                        sample_rate=sample_rate,
                    )
                if url:
                    final_url = url
        except Exception as exc:  # noqa: BLE001
            logger.exception("DashScope TTS stream iteration failed")
            yield TtsChunk(
                event="error",
                sentence_index=sentence_index,
                text=text,
                error=str(exc),
            )
            return

        if not saw_delta and not final_url:
            yield TtsChunk(
                event="error",
                sentence_index=sentence_index,
                text=text,
                error="empty_audio_stream",
            )
            return

        yield TtsChunk(
            event="sentence_end",
            sentence_index=sentence_index,
            text=text,
            audio_url=final_url,
            mime="audio/wav" if final_url else mime,
            sample_rate=sample_rate,
        )
