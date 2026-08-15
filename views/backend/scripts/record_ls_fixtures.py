"""录制 LS E4 用的 skill 响应样本。

优先用 views/run.py 的 LLM/ASR 配置 + 公网媒体实打 HTTP。
厂商失败时回退到生产 envelope + mapper，保证目录不空。
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

VIEWS_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = VIEWS_ROOT / "shared" / "ls-fixtures"
LIVE_AUDIO_URL = "https://assets.julebu.co/videos/6fbe4624-3fb4-4a8a-8c33-5f1aa617c35c.mp4"

if str(VIEWS_ROOT) not in sys.path:
    sys.path.insert(0, str(VIEWS_ROOT))

from run import _env  # noqa: E402

os.environ.update(_env())
os.environ["AGENT_AUTH_DISABLED"] = "1"

from backend.agents import get_agent  # noqa: E402
from backend.agents.envelope import build_envelope, error_payload  # noqa: E402
from backend.agents.loader import AGENTS_ROOT  # noqa: E402
from backend.app import create_app  # noqa: E402

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from _lib.asr.format import to_transcribe_output  # noqa: E402
from _lib.asr.types import AsrResult, AsrSentence, AsrWord  # noqa: E402

RECORDED_AT = date.today().isoformat()
LS_KEYS = ("request_id", "skill", "output", "usage", "versions", "error")
FALLBACK_SENTENCE = "We're in a competitive industry."
FALLBACK_ZH = "我们处在一个竞争激烈的行业。"

LIVE: dict[str, Any] = {
    "text": FALLBACK_SENTENCE,
    "cues": [
        {"text": "I am.", "start_ms": 21805, "end_ms": 23000},
        {"text": FALLBACK_SENTENCE, "start_ms": 23010, "end_ms": 25900},
    ],
    "language": "en",
    "asr_ok": False,
}


def _ls_body(data: dict[str, Any]) -> dict[str, Any]:
    return {k: data[k] for k in LS_KEYS if k in data}


def _write(rel: str, payload: dict[str, Any]) -> Path:
    path = OUT_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _case(
    *,
    skill: str,
    title: str,
    notes: str,
    status: int,
    request_id: str,
    body: dict[str, Any],
    response: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    return {
        "skill": skill,
        "title": title,
        "notes": notes,
        "recorded_at": RECORDED_AT,
        "source": source,
        "http": {
            "method": "POST",
            "path": f"/api/agents/{skill}/run",
            "status": status,
        },
        "request": {
            "headers": {
                "Content-Type": "application/json",
                "X-Internal-Token": "<AGENT_TOKEN>",
            },
            "body": {"request_id": request_id, **body},
        },
        "response": response,
    }


def _envelope(skill: str, request_id: str, user_input: Any, result: dict[str, Any], latency_ms: int) -> dict[str, Any]:
    spec = get_agent(skill)
    if spec is None:
        raise KeyError(skill)
    raw = build_envelope(
        spec=spec,
        request_id=request_id,
        user_input=user_input,
        result=result,
        latency_ms=latency_ms,
    )
    return _ls_body(raw)


def _http(skill: str, body: dict[str, Any], *, token: str | None = None, auth_disabled: bool = True) -> tuple[int, dict[str, Any]]:
    os.environ["AGENT_AUTH_DISABLED"] = "1" if auth_disabled else "0"
    if token is not None:
        os.environ["INTERNAL_TOKEN"] = token
        os.environ["AGENT_AUTH_DISABLED"] = "0"
    app = create_app()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Internal-Token"] = token
    with app.test_client() as client:
        res = client.post(f"/api/agents/{skill}/run", json=body, headers=headers)
    data = res.get_json() or {}
    return res.status_code, _ls_body(data) if isinstance(data, dict) else {"error": data}


def _looks_latin(text: str) -> bool:
    letters = re.findall(r"[A-Za-z]", text or "")
    return len(letters) >= 8


def _pick_sentence(cues: list[dict[str, Any]], text: str) -> str:
    for cue in cues:
        piece = str(cue.get("text") or "").strip()
        if len(piece) >= 12:
            return piece
    for piece in re.split(r"(?<=[。！？.!?])\s*", text or ""):
        if len(piece.strip()) >= 12:
            return piece.strip()
    return (text or FALLBACK_SENTENCE).strip()[:180] or FALLBACK_SENTENCE


def _pick_lemma(sentence: str, language: str) -> tuple[str, str]:
    if language.startswith("zh"):
        return "行业", sentence
    words = re.findall(r"[A-Za-z]{4,}", sentence)
    stop = {
        "that", "this", "with", "from", "have", "were", "we're", "been",
        "what", "your", "name", "they", "them", "their", "there", "here",
        "just", "into", "about",
    }
    for w in words:
        if w.lower() not in stop:
            return w.lower(), sentence
    return "industry", sentence


def _asr_fallback_output(*, words: bool) -> dict[str, Any]:
    result = AsrResult(
        transcript=f"I am. {FALLBACK_SENTENCE}",
        sentences=[
            AsrSentence(
                index=0,
                text="I am.",
                start_ms=21805,
                end_ms=23000,
                words=[
                    AsrWord(text="I", start_ms=21805, end_ms=21910, confidence=0.98),
                    AsrWord(text="am", start_ms=21920, end_ms=22980, confidence=0.97),
                ],
            ),
            AsrSentence(
                index=1,
                text=FALLBACK_SENTENCE,
                start_ms=23010,
                end_ms=25900,
                words=[
                    AsrWord(text="We're", start_ms=23010, end_ms=23240, confidence=0.96),
                    AsrWord(text="in", start_ms=23250, end_ms=23380, confidence=0.99),
                    AsrWord(text="a", start_ms=23390, end_ms=23460, confidence=0.99),
                    AsrWord(text="competitive", start_ms=23470, end_ms=24800, confidence=0.95),
                    AsrWord(text="industry", start_ms=24810, end_ms=25900, confidence=0.97),
                ],
            ),
        ],
    )
    return to_transcribe_output(result, enable_word_timestamps=words)


def record_asr() -> list[str]:
    files: list[str] = []
    rid = "01JFIXASR000000000000001"
    body = {
        "audio_url": LIVE_AUDIO_URL,
        "language": "zh-CN",
        "enable_word_timestamps": True,
    }
    print("ASR live: submitting video (may take a few minutes)…", flush=True)
    status, data = _http("asr.transcribe", {"request_id": rid, **body})
    source = "http"
    if status != 200 or not (data.get("output") or {}).get("text"):
        print(f"ASR live failed status={status} error={data.get('error')}; using mapper fallback", flush=True)
        data = _envelope(
            "asr.transcribe",
            rid,
            "",
            {
                "output": _asr_fallback_output(words=True),
                "usage": {
                    "provider": "aliyun",
                    "model": "paraformer-v2",
                    "tokens": 0,
                    "usage_sec": 25.9,
                    "cost_micros": None,
                },
                "meta": {"package_version": "1.2.0"},
            },
            4100,
        )
        source = "envelope+to_transcribe_output"
        status = 200
    else:
        LIVE["asr_ok"] = True
        print(f"ASR live ok, text[:80]={str(data['output'].get('text') or '')[:80]!r}", flush=True)

    out = data.get("output") or {}
    LIVE["text"] = str(out.get("text") or FALLBACK_SENTENCE)
    LIVE["cues"] = list(out.get("cues") or LIVE["cues"])
    LIVE["language"] = "en" if _looks_latin(LIVE["text"]) else "zh-CN"

    files.append("asr.transcribe/200-en-cues-no-id.json")
    _write(
        files[-1],
        _case(
            skill="asr.transcribe",
            title="公网视频转写 · cues 无 id · cost_micros=null",
            notes=(
                "真实/回退转写。cues 只有 text/start_ms/end_ms，没有 id。"
                "LS 对齐用时间戳。usage.cost_micros 本期为 null。"
            ),
            status=status,
            request_id=rid,
            body=body,
            response=data,
            source=source,
        ),
    )

    sentence_out = dict(out)
    sentence_out["words"] = []
    sentence_out["timestamp_granularity"] = "sentence"
    rid2 = "01JFIXASR000000000000002"
    files.append("asr.transcribe/200-en-sentence-granularity.json")
    _write(
        files[-1],
        _case(
            skill="asr.transcribe",
            title="同一转写 · 仅句级时间戳",
            notes="同一份 live output，去掉 words。cues 仍无 id。",
            status=200,
            request_id=rid2,
            body={
                "audio_url": LIVE_AUDIO_URL,
                "language": "zh-CN",
                "enable_word_timestamps": False,
            },
            response=_envelope(
                "asr.transcribe",
                rid2,
                "",
                {
                    "output": sentence_out or _asr_fallback_output(words=False),
                    "usage": data.get("usage")
                    or {
                        "provider": "aliyun",
                        "model": "paraformer-v2",
                        "tokens": 0,
                        "usage_sec": 0,
                        "cost_micros": None,
                    },
                    "meta": {"package_version": "1.2.0"},
                },
                int((data.get("usage") or {}).get("latency_ms") or 2800),
            ),
            source="http+strip-words" if LIVE["asr_ok"] else "envelope+to_transcribe_output",
        ),
    )

    ja = to_transcribe_output(
        AsrResult(
            transcript="競争の激しい業界です。",
            sentences=[
                AsrSentence(
                    index=0,
                    text="競争の激しい業界です。",
                    start_ms=120,
                    end_ms=2410,
                    words=[
                        AsrWord(text="競争", start_ms=120, end_ms=520, confidence=0.94),
                        AsrWord(text="の", start_ms=530, end_ms=610, confidence=0.99),
                        AsrWord(text="激しい", start_ms=620, end_ms=1100, confidence=0.93),
                        AsrWord(text="業界", start_ms=1110, end_ms=1680, confidence=0.95),
                        AsrWord(text="です", start_ms=1690, end_ms=2410, confidence=0.98),
                    ],
                )
            ],
        ),
        enable_word_timestamps=True,
    )
    rid3 = "01JFIXASR000000000000003"
    files.append("asr.transcribe/200-ja-word.json")
    _write(
        files[-1],
        _case(
            skill="asr.transcribe",
            title="日文转写（mapper 样本）",
            notes="本期只有一条中文视频，日文包仍用生产 mapper 录形状。",
            status=200,
            request_id=rid3,
            body={
                "audio_url": "https://example.com/signed/clip-ja.mp3",
                "language": "ja",
                "enable_word_timestamps": True,
            },
            response=_envelope(
                "asr.transcribe",
                rid3,
                "",
                {
                    "output": ja,
                    "usage": {
                        "provider": "aliyun",
                        "model": "paraformer-v2",
                        "tokens": 0,
                        "usage_sec": 2.41,
                        "cost_micros": None,
                    },
                    "meta": {"package_version": "1.2.0"},
                },
                1600,
            ),
            source="envelope+to_transcribe_output",
        ),
    )

    saved_key = os.environ.get("DASHSCOPE_API_KEY", "")
    os.environ["DASHSCOPE_API_KEY"] = ""
    rid4 = "01JFIXASR000000000000004"
    status4, data4 = _http(
        "asr.transcribe",
        {"request_id": rid4, "audio_url": LIVE_AUDIO_URL, "language": "zh-CN"},
    )
    os.environ["DASHSCOPE_API_KEY"] = saved_key
    files.append("asr.transcribe/400-asr-unavailable.json")
    _write(
        files[-1],
        _case(
            skill="asr.transcribe",
            title="ASR 未配置",
            notes="临时清空 DASHSCOPE_API_KEY 后的真实 HTTP 400。LS 不要重试。",
            status=status4,
            request_id=rid4,
            body={"audio_url": LIVE_AUDIO_URL, "language": "zh-CN"},
            response=data4,
            source="http",
        ),
    )
    return files


def record_translate() -> list[str]:
    files: list[str] = []
    src_lang = LIVE["language"]
    tgt_lang = "en" if src_lang.startswith("zh") else "zh-CN"
    items = []
    for i, cue in enumerate(LIVE["cues"][:4]):
        text = str(cue.get("text") or "").strip()
        if not text:
            continue
        items.append(
            {
                "id": f"c{i + 1}",
                "text": text,
                "start_ms": cue.get("start_ms"),
                "end_ms": cue.get("end_ms"),
            }
        )
    if not items:
        items = [{"id": "c1", "text": FALLBACK_SENTENCE, "start_ms": 23010, "end_ms": 25900}]

    rid = "01JFIXTR0000000000000001"
    body = {"source_lang": src_lang, "target_lang": tgt_lang, "items": items}
    print("translate live…", flush=True)
    status, data = _http("translate", {"request_id": rid, **body})
    source = "http"
    if status != 200:
        print(f"translate live status={status} error={data.get('error')}", flush=True)
        mod = get_agent("translate")["module"]
        aligned = mod.align_translations(
            items,
            [{"id": it["id"], "text": FALLBACK_ZH if tgt_lang.startswith("zh") else FALLBACK_SENTENCE} for it in items],
        )
        data = _envelope(
            "translate",
            rid,
            "",
            {
                "output": {"items": aligned},
                "usage": {"provider": "llm", "model": "deepseek-chat", "tokens": 120, "usage_sec": 0, "cost_micros": None},
                "meta": {"package_version": "1.0.0"},
            },
            900,
        )
        status = 200
        source = "envelope+align_translations"

    files.append("translate/200-items.json")
    _write(
        files[-1],
        _case(
            skill="translate",
            title="带时间戳片段",
            notes="id / start_ms / end_ms 原样回传。cost_micros=null。",
            status=status,
            request_id=rid,
            body=body,
            response=data,
            source=source,
        ),
    )

    rid2 = "01JFIXTR0000000000000002"
    text = _pick_sentence(LIVE["cues"], LIVE["text"])
    body2 = {"source_lang": src_lang, "target_lang": tgt_lang, "text": text}
    status2, data2 = _http("translate", {"request_id": rid2, **body2})
    source2 = "http"
    if status2 != 200:
        mod = get_agent("translate")["module"]
        aligned = mod.align_translations(
            [{"id": "t1", "text": text, "start_ms": None, "end_ms": None}],
            [{"id": "t1", "text": FALLBACK_ZH if tgt_lang.startswith("zh") else FALLBACK_SENTENCE}],
        )
        data2 = _envelope(
            "translate",
            rid2,
            text,
            {
                "output": {"items": aligned},
                "usage": {"provider": "llm", "model": "deepseek-chat", "tokens": 40, "usage_sec": 0, "cost_micros": None},
                "meta": {"package_version": "1.0.0"},
            },
            700,
        )
        status2 = 200
        source2 = "envelope+align_translations"
    files.append("translate/200-plain-text.json")
    _write(
        files[-1],
        _case(
            skill="translate",
            title="整段 text",
            notes="无时间戳时 start_ms/end_ms 为 null，id 仍回传。",
            status=status2,
            request_id=rid2,
            body=body2,
            response=data2,
            source=source2,
        ),
    )

    rid3 = "01JFIXTR0000000000000003"
    status3, data3 = _http("translate", {"request_id": rid3, "source_lang": "en", "target_lang": "zh-CN"})
    files.append("translate/400-empty.json")
    _write(
        files[-1],
        _case(
            skill="translate",
            title="缺 items/text",
            notes="真实 HTTP 400，LS 不要重试。",
            status=status3,
            request_id=rid3,
            body={"source_lang": "en", "target_lang": "zh-CN"},
            response=data3,
            source="http",
        ),
    )
    return files


def record_extract() -> list[str]:
    files: list[str] = []
    lang = LIVE["language"]
    cues_with_id = []
    for i, cue in enumerate(LIVE["cues"][:8]):
        text = str(cue.get("text") or "").strip()
        if not text:
            continue
        cues_with_id.append(
            {
                "id": f"c{i + 1}",
                "text": text,
                "start_ms": cue.get("start_ms"),
                "end_ms": cue.get("end_ms"),
            }
        )
    rid = "01JFIXEX0000000000000001"
    body = {"learning_language": lang, "cues": cues_with_id or LIVE["cues"]}
    status, data = _http("sentence.extract", {"request_id": rid, **body})
    files.append("sentence.extract/200-cues.json")
    _write(
        files[-1],
        _case(
            skill="sentence.extract",
            title="从带 id 的 cue 拆句",
            notes="实打 HTTP。cue_ids 回传请求里的 id。",
            status=status,
            request_id=rid,
            body=body,
            response=data,
            source="http",
        ),
    )

    rid2 = "01JFIXEX0000000000000002"
    text = LIVE["text"]
    body2 = {"learning_language": lang, "text": text}
    status2, data2 = _http("sentence.extract", {"request_id": rid2, **body2})
    files.append("sentence.extract/200-text-empty-cue-ids.json")
    _write(
        files[-1],
        _case(
            skill="sentence.extract",
            title="纯文本拆句 · cue_ids 为空",
            notes="无 cues 时 start_ms/end_ms 为 null，cue_ids=[]。",
            status=status2,
            request_id=rid2,
            body=body2,
            response=data2,
            source="http",
        ),
    )

    asr_cues = [
        {"text": c.get("text"), "start_ms": c.get("start_ms"), "end_ms": c.get("end_ms")}
        for c in LIVE["cues"][:8]
        if str(c.get("text") or "").strip()
    ]
    rid3 = "01JFIXEX0000000000000003"
    body3 = {"learning_language": lang, "cues": asr_cues}
    status3, data3 = _http("sentence.extract", {"request_id": rid3, **body3})
    files.append("sentence.extract/200-asr-cues-no-id.json")
    _write(
        files[-1],
        _case(
            skill="sentence.extract",
            title="吃 ASR cues（无 id）",
            notes="请求 cues 无 id 时 Agent 会补 c0/c1。LS 若自己对齐，仍以时间戳为准。",
            status=status3,
            request_id=rid3,
            body=body3,
            response=data3,
            source="http",
        ),
    )
    return files


def record_analyze() -> list[str]:
    files: list[str] = []
    sentence = _pick_sentence(LIVE["cues"], LIVE["text"])
    if not _looks_latin(sentence):
        sentence = FALLBACK_SENTENCE
        learn, support = "en", "zh-CN"
        note_extra = "视频转写偏中文，句析仍用英文句（en-syntax-tagger 只分析英语）。"
    else:
        learn, support = "en", "zh-CN"
        note_extra = "句子取自本次转写。"
    packs = (
        ("v1", "01JFIXAN0000000000000001", "200-v1.json"),
        ("v2", "01JFIXAN0000000000000002", "200-v2.json"),
        ("v3", "01JFIXAN0000000000000003", "200-v3.json"),
    )
    for version, rid, name in packs:
        body = {
            "text": sentence,
            "api_version": version,
            "learning_language": learn,
            "support_language": support,
            "user_level": "B1",
            "goal": "商务口语",
        }
        print(f"sentence.analyze {version} live…", flush=True)
        status, data = _http("sentence.analyze", {"request_id": rid, **body})
        source = "http"
        if status != 200 or not (data.get("output") or {}).get("api_version"):
            print(f"analyze {version} status={status} error={data.get('error')}", flush=True)
            to_out = get_agent("sentence.analyze")["module"].to_versioned_ls_output
            ls_out = to_out(
                {
                    "input": sentence,
                    "api_version": version,
                    "analysis": {"sentence": sentence, "translation": FALLBACK_ZH},
                    "spacy_tokens": [],
                    "meta": {"agent": "en-syntax-tagger", "package_version": "3.0.0"},
                },
                api_version=version,
                learning_language=learn,
                support_language=support,
                profile="academic" if version == "v1" else "teaching" if version == "v2" else "json",
                user_level="B1",
                goal="商务口语",
            )
            data = _envelope(
                "sentence.analyze",
                rid,
                sentence,
                {
                    "output": ls_out,
                    "usage": {"provider": "llm", "model": "deepseek-chat", "tokens": 0, "usage_sec": 0, "cost_micros": None},
                    "meta": {"package_version": "3.0.0"},
                },
                1200,
            )
            status = 200
            source = "envelope+to_versioned_ls_output"
        files.append(f"sentence.analyze/{name}")
        _write(
            files[-1],
            _case(
                skill="sentence.analyze",
                title=f"单句分析 {version}",
                notes=f"output.api_version={version}。{note_extra} 无 activity_id。",
                status=status,
                request_id=rid,
                body=body,
                response=data,
                source=source,
            ),
        )
    return files


def record_vocab() -> list[str]:
    files: list[str] = []
    sentence = _pick_sentence(LIVE["cues"], LIVE["text"])
    lemma, context = _pick_lemma(sentence if _looks_latin(sentence) else FALLBACK_SENTENCE, "en")
    rid = "01JFIXVC0000000000000001"
    body = {
        "lemma": lemma,
        "context": context,
        "learning_language": "en",
        "support_language": "zh-CN",
        "user_level": "C1",
        "goal": "商务口语",
    }
    print(f"vocabulary.generate live lemma={lemma!r}…", flush=True)
    status, data = _http("vocabulary.generate", {"request_id": rid, **body})
    source = "http"
    if status != 200:
        mod = get_agent("vocabulary-generate")["module"]
        card = mod.normalize_card(
            {
                "lemma": "emotive",
                "phonetic": {"notation": "IPA", "value": "ɪˈməʊtɪv"},
                "pos": ["adj"],
                "level": "C1",
                "senses": [
                    {
                        "sense_id": "s1",
                        "gloss": {"zh-CN": "易引起强烈感情的", "en": "arousing intense feeling"},
                        "example_texts": [{"lang": "en", "text": "an emotive issue"}],
                    }
                ],
            },
            lemma="emotive",
            learning="en",
            support="zh-CN",
            user_level="C1",
            context="an emotive issue",
        )
        data = _envelope(
            "vocabulary.generate",
            rid,
            lemma,
            {
                "output": card,
                "usage": {"provider": "llm", "model": "deepseek-chat", "tokens": 200, "usage_sec": 0, "cost_micros": None},
                "meta": {"package_version": "1.0.0"},
            },
            1100,
        )
        status = 200
        source = "envelope+normalize_card"
        body["lemma"] = "emotive"
        body["context"] = "an emotive issue"
    files.append("vocabulary.generate/200-emotive.json")
    _write(
        files[-1],
        _case(
            skill="vocabulary.generate",
            title=f"词条 {body['lemma']} · cost_micros=null",
            notes="例句为文本。禁止 object_id。cost_micros=null。",
            status=status,
            request_id=rid,
            body=body,
            response=data,
            source=source,
        ),
    )

    rid2 = "01JFIXVC0000000000000002"
    body2 = {
        "lemma": "industry",
        "context": FALLBACK_SENTENCE,
        "learning_language": "en",
        "support_language": "zh-CN",
        "user_level": "B1",
        "goal": "商务口语",
    }
    status2, data2 = _http("vocabulary.generate", {"request_id": rid2, **body2})
    source2 = "http"
    if status2 != 200:
        mod = get_agent("vocabulary-generate")["module"]
        card2 = mod.normalize_card(
            {
                "lemma": "industry",
                "phonetic": {"notation": "IPA", "value": "ˈɪndəstri"},
                "pos": ["noun"],
                "level": "B1",
                "senses": [
                    {
                        "sense_id": "s1",
                        "gloss": {"zh-CN": "行业；产业", "en": "a competitive industry"},
                        "example_texts": [{"lang": "en", "text": "a competitive industry"}],
                    }
                ],
            },
            lemma="industry",
            learning="en",
            support="zh-CN",
            user_level="B1",
            context=FALLBACK_SENTENCE,
        )
        data2 = _envelope(
            "vocabulary.generate",
            rid2,
            "industry",
            {
                "output": card2,
                "usage": {"provider": "llm", "model": "deepseek-chat", "tokens": 160, "usage_sec": 0, "cost_micros": None},
                "meta": {"package_version": "1.0.0"},
            },
            980,
        )
        status2 = 200
        source2 = "envelope+normalize_card"
    files.append("vocabulary.generate/200-industry.json")
    _write(
        files[-1],
        _case(
            skill="vocabulary.generate",
            title="词条 industry",
            notes="第二份词条，方便 LS 测列表渲染。",
            status=status2,
            request_id=rid2,
            body=body2,
            response=data2,
            source=source2,
        ),
    )

    rid3 = "01JFIXVC0000000000000003"
    status3, data3 = _http("vocabulary.generate", {"request_id": rid3, "learning_language": "en"})
    files.append("vocabulary.generate/400-empty.json")
    _write(
        files[-1],
        _case(
            skill="vocabulary.generate",
            title="缺 lemma",
            notes="真实 HTTP 400。",
            status=status3,
            request_id=rid3,
            body={"learning_language": "en"},
            response=data3,
            source="http",
        ),
    )
    return files


def record_errors() -> list[str]:
    files: list[str] = []
    os.environ["INTERNAL_TOKEN"] = "secret-ls"
    os.environ["AGENT_AUTH_DISABLED"] = "0"
    app = create_app()
    with app.test_client() as client:
        res = client.post(
            "/api/agents/translate/run",
            json={"request_id": "01JFIXERR00000000000001", "text": "hi"},
        )
    files.append("_errors/401-unauthorized.json")
    _write(
        files[-1],
        {
            "skill": "translate",
            "title": "缺内部 token",
            "notes": "设了 INTERNAL_TOKEN 且未带头时的真实 401。LS 不要重试。",
            "recorded_at": RECORDED_AT,
            "source": "http",
            "http": {"method": "POST", "path": "/api/agents/translate/run", "status": res.status_code},
            "request": {
                "headers": {"Content-Type": "application/json"},
                "body": {"request_id": "01JFIXERR00000000000001", "text": "hi"},
            },
            "response": res.get_json() or error_payload("unauthorized", "missing or invalid X-Internal-Token"),
        },
    )
    os.environ["AGENT_AUTH_DISABLED"] = "1"
    status, data = _http("not.a.skill", {"request_id": "01JFIXERR00000000000002"})
    files.append("_errors/404-unknown-skill.json")
    _write(
        files[-1],
        {
            "skill": "not.a.skill",
            "title": "未知 skill",
            "notes": "真实 HTTP 404。",
            "recorded_at": RECORDED_AT,
            "source": "http",
            "http": {"method": "POST", "path": "/api/agents/not.a.skill/run", "status": status},
            "request": {
                "headers": {"Content-Type": "application/json", "X-Internal-Token": "<AGENT_TOKEN>"},
                "body": {"request_id": "01JFIXERR00000000000002"},
            },
            "response": data,
        },
    )
    return files


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    files.extend(record_asr())
    files.extend(record_translate())
    files.extend(record_extract())
    files.extend(record_analyze())
    files.extend(record_vocab())
    files.extend(record_errors())

    index = {
        "version": "1",
        "recorded_at": RECORDED_AT,
        "base_path": "/api/agents/{skill}/run",
        "audio_url": LIVE_AUDIO_URL,
        "notes": (
            "给 LS E4 薄客户端 / Gateway 的录制样本。"
            "优先用 run.py 的 LLM/ASR 配置实打；失败才回退 mapper。"
            "response 只含 request_id/skill/output/usage/versions（及 4xx 的 error）。"
        ),
        "fixtures": [],
    }
    for rel in files:
        data = json.loads((OUT_DIR / rel).read_text(encoding="utf-8"))
        index["fixtures"].append(
            {
                "file": rel,
                "skill": data.get("skill"),
                "status": (data.get("http") or {}).get("status"),
                "title": data.get("title"),
                "source": data.get("source"),
            }
        )
    _write("index.json", index)
    print(f"wrote {len(files)} fixtures + index under {OUT_DIR}")


if __name__ == "__main__":
    main()
