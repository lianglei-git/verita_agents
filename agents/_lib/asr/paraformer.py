"""阿里云 Paraformer 录音文件转写（异步 Transcription）。"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.request import Request, urlopen

from _lib.asr.config import AsrConfig
from _lib.asr.errors import AsrError
from _lib.asr.types import AsrResult, AsrSentence, AsrWord

logger = logging.getLogger(__name__)

__all__ = ["AsrError", "is_asr_available", "transcribe_url"]


def is_asr_available(cfg: AsrConfig | None = None) -> bool:
    cfg = cfg or AsrConfig()
    return not cfg.disabled and bool(cfg.api_key)


def _to_ms(value: Any) -> int | None:
    if value is None:
        return None
    try:
        # Paraformer times are usually milliseconds already
        n = int(value)
        return n
    except (TypeError, ValueError):
        return None


def _parse_words(raw_words: Any) -> list[AsrWord]:
    if not isinstance(raw_words, list):
        return []
    out: list[AsrWord] = []
    for w in raw_words:
        if not isinstance(w, dict):
            continue
        text = str(w.get("text") or "")
        if not text and not w.get("punctuation"):
            continue
        confidence = w.get("confidence")
        if confidence is None:
            confidence = w.get("confidence_score")
        try:
            confidence_f = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence_f = None
        out.append(
            AsrWord(
                text=text,
                start_ms=_to_ms(w.get("begin_time")),
                end_ms=_to_ms(w.get("end_time")),
                punctuation=str(w.get("punctuation") or ""),
                confidence=confidence_f,
            )
        )
    return out


def _parse_sentences(payload: Any) -> list[AsrSentence]:
    sentences: list[AsrSentence] = []
    if not isinstance(payload, dict):
        return sentences

    transcripts = payload.get("transcripts") or payload.get("results") or []
    if not isinstance(transcripts, list):
        # sometimes output is already a list of files
        return sentences

    idx = 0
    for tr in transcripts:
        if not isinstance(tr, dict):
            continue
        sents = tr.get("sentences") or []
        if not isinstance(sents, list):
            continue
        for s in sents:
            if not isinstance(s, dict):
                continue
            text = str(s.get("text") or "").strip()
            if not text:
                continue
            sentences.append(
                AsrSentence(
                    index=idx,
                    text=text,
                    start_ms=_to_ms(s.get("begin_time")),
                    end_ms=_to_ms(s.get("end_time")),
                    words=_parse_words(s.get("words")),
                )
            )
            idx += 1
    return sentences


def _download_json(url: str, *, timeout: float = 60.0) -> Any:
    req = Request(url, headers={"User-Agent": "verita-asr/1.0"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _extract_transcription_payload(output: Any) -> dict[str, Any]:
    """
    Transcription.wait output may embed results or point to transcription_url.
    Normalize to a dict containing transcripts[].sentences[].
    """
    if output is None:
        return {}
    if hasattr(output, "get"):
        data = dict(output) if not isinstance(output, dict) else output
    elif hasattr(output, "__dict__"):
        data = getattr(output, "__dict__", {}) or {}
    else:
        try:
            data = json.loads(json.dumps(output, default=str))
        except Exception:  # noqa: BLE001
            data = {}

    if not isinstance(data, dict):
        return {}

    # Direct transcripts
    if data.get("transcripts") or data.get("sentences"):
        return data

    results = data.get("results")
    if isinstance(results, list) and results:
        merged_transcripts: list[dict] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            turl = item.get("transcription_url") or item.get("url")
            if turl:
                try:
                    remote = _download_json(str(turl))
                    if isinstance(remote, dict):
                        if remote.get("transcripts"):
                            merged_transcripts.extend(remote["transcripts"])
                        elif remote.get("sentences"):
                            merged_transcripts.append({"sentences": remote["sentences"]})
                        else:
                            merged_transcripts.append(remote)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("download transcription_url failed: %s", exc)
            elif item.get("transcripts"):
                merged_transcripts.extend(item["transcripts"])
            elif item.get("sentences"):
                merged_transcripts.append({"sentences": item["sentences"]})
        if merged_transcripts:
            return {"transcripts": merged_transcripts}

    return data


def transcribe_url(
    file_url: str,
    cfg: AsrConfig | None = None,
    *,
    language: str | None = None,
) -> AsrResult:
    """Submit Paraformer async job for a publicly reachable audio/video URL."""
    from _lib.asr.languages import language_hints_for

    cfg = cfg or AsrConfig()
    if not is_asr_available(cfg):
        raise AsrError("asr_unavailable")
    url = (file_url or "").strip()
    if not url:
        raise AsrError("empty_audio_url")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise AsrError("audio_url_must_be_http")

    try:
        import dashscope
        from dashscope.audio.asr import Transcription
        from http import HTTPStatus
    except ImportError as exc:
        raise AsrError("dashscope package not installed") from exc

    dashscope.api_key = cfg.api_key
    dashscope.base_http_api_url = cfg.base_http_api_url
    hints = language_hints_for(language, cfg.language_hints)

    try:
        model = cfg.subtitle_model or cfg.model
        task_response = Transcription.async_call(
            model=model,
            file_urls=[url],
            language_hints=hints,
            timestamp_alignment_enabled=True,
        )
    except TypeError:
        # older SDK may not accept timestamp_alignment_enabled
        model = cfg.subtitle_model or cfg.model
        task_response = Transcription.async_call(
            model=model,
            file_urls=[url],
            language_hints=hints,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Paraformer async_call failed")
        raise AsrError(str(exc)) from exc

    task_id = None
    if task_response and getattr(task_response, "output", None) is not None:
        task_id = getattr(task_response.output, "task_id", None)
        if task_id is None and isinstance(task_response.output, dict):
            task_id = task_response.output.get("task_id")

    if not task_id:
        raise AsrError(
            f"paraformer_submit_failed: {getattr(task_response, 'message', task_response)}"
        )

    try:
        transcribe_response = Transcription.wait(task=task_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Paraformer wait failed")
        raise AsrError(str(exc)) from exc

    status = getattr(transcribe_response, "status_code", None)
    if status is not None and int(status) != int(HTTPStatus.OK):
        raise AsrError(
            getattr(transcribe_response, "message", None)
            or f"paraformer_failed_status_{status}"
        )

    output = getattr(transcribe_response, "output", None)
    # task failed?
    task_status = getattr(output, "task_status", None)
    if task_status is None and isinstance(output, dict):
        task_status = output.get("task_status")
    if task_status and str(task_status).upper() == "FAILED":
        raise AsrError(f"paraformer_task_failed: {output}")

    payload = _extract_transcription_payload(output)
    sentences = _parse_sentences(payload)
    if not sentences and isinstance(payload, dict):
        # fallback: single text field
        text = payload.get("text") or payload.get("transcription")
        if text:
            sentences = [AsrSentence(index=0, text=str(text))]

    transcript = "".join(s.text for s in sentences) if sentences else ""
    if not transcript and sentences:
        transcript = " ".join(s.text for s in sentences)

    return AsrResult(transcript=transcript, sentences=sentences, raw=payload)
