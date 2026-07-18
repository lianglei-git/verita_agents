"""Life Script Author — 分章人生剧本创作 Agent。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parent
_AGENTS_ROOT = _AGENT_DIR.parent
for path in (_AGENTS_ROOT, _AGENT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from lsa_chapter_writer import generate_chapter_draft, generate_chapter_plan  # noqa: E402
from lsa_continuity_editor import apply_draft_to_bible, run_continuity_check  # noqa: E402
from lsa_contract import (  # noqa: E402
    CHAPTER_CONTINUITY,
    CHAPTER_DRAFT,
    CHAPTER_PLAN,
    CHAPTER_SUB_LABELS,
    CHAPTER_UPDATE,
    MID_REVIEW_INTERVAL,
    PHASE_BIBLE,
    PHASE_CHAPTER,
    PHASE_COMPLETE,
    PHASE_LABELS,
    PHASE_MID_REVIEW,
    PHASE_OUTLINE,
    PHASE_SETUP,
)
from lsa_llm import begin_turn, drain_calls  # noqa: E402
from lsa_outline_planner import (  # noqa: E402
    apply_setup_answer,
    ensure_setup_questions,
    finalize_setup,
    generate_outline,
    generate_story_bible,
    setup_all_answered,
)
from lsa_state import (  # noqa: E402
    all_chapters_complete,
    append_llm_calls,
    chapter_subphase,
    current_chapter_number,
    empty_session,
    normalize_session,
    record_turn,
    set_bible,
    set_chapter_work,
    set_outline,
    set_phase,
    set_setup,
    setup_complete,
    total_chapters,
)

try:
    from _lib.llm import is_llm_available  # noqa: E402
except ImportError:

    def is_llm_available() -> bool:  # type: ignore[misc]
        return False


def _parse_payload(user_input: str, kwargs: dict) -> dict:
    if kwargs:
        return kwargs
    if not user_input.strip():
        return {}
    try:
        data = json.loads(user_input)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"message": user_input}


def _active_setup_question(session: dict) -> dict | None:
    pending = (session.get("setup") or {}).get("pending_questions") or []
    answers = (session.get("setup") or {}).get("answers") or {}
    for q in pending:
        if q["id"] not in answers:
            return q
    return None


def _ingest_handoff(session: dict, payload: dict) -> dict:
    handoff = dict(session.get("handoff") or {})
    for key in ("planning_profile", "scenario_set", "scenario_id", "gap_diagnosis"):
        if payload.get(key) is not None:
            handoff[key] = payload[key]
    if payload.get("handoff"):
        handoff.update(payload["handoff"])
    session = normalize_session({**session, "handoff": handoff})
    return session


def _summary(session: dict) -> str:
    phase = session.get("current_phase") or PHASE_SETUP
    label = PHASE_LABELS.get(phase, phase)
    if phase == PHASE_CHAPTER:
        sub = chapter_subphase(session)
        n = current_chapter_number(session)
        total = total_chapters(session)
        sub_label = CHAPTER_SUB_LABELS.get(sub, sub)
        return f"{label} · 第{n}/{total}章 · {sub_label}"
    if phase == PHASE_COMPLETE:
        done = len((session.get("chapter_work") or {}).get("completed") or [])
        return f"{label} · 共 {done} 章"
    return label


def _run_setup(session: dict, payload: dict) -> tuple[dict, str, dict]:
    meta: dict[str, Any] = {"source": "setup"}

    if payload.get("setup_patch") and isinstance(payload["setup_patch"], dict):
        patch = payload["setup_patch"]
        ci_patch = patch.pop("creative_intent", None)
        if ci_patch:
            session = set_setup(session, creative_intent=ci_patch)
        if patch:
            session = set_setup(session, **patch)

    answer = payload.get("answer")
    if isinstance(answer, dict) and answer.get("question_id"):
        session = apply_setup_answer(session, answer)

    if payload.get("skip_setup_questions") and payload.get("creative_intent"):
        session = set_setup(
            session,
            creative_intent=payload["creative_intent"],
            adaptation_mode=payload.get("adaptation_mode", "deidentified"),
            status="complete",
        )
        meta["source"] = "setup_skip"
        return session, "创作意图已记录，将生成故事圣经。", meta

    session = ensure_setup_questions(session)

    if setup_all_answered(session):
        session = finalize_setup(session)
        meta["source"] = "setup_complete"
        return session, "创作意图已确认。正在进入故事圣经阶段…", meta

    q = _active_setup_question(session)
    if q:
        meta["active_question"] = q
        return session, f"请先确认创作意图：{q['text']}", meta

    return session, "请补充创作意图信息。", meta


def _run_bible(session: dict, payload: dict) -> tuple[dict, str, dict]:
    meta: dict[str, Any] = {"source": "bible"}

    if not session.get("story_bible"):
        bible, issues = generate_story_bible(session)
        session = set_bible(session, bible, approved=False)
        meta["validation_issues"] = issues
        meta["source"] = "bible_generated"
        return (
            session,
            "故事圣经初稿已生成。请审阅 `story_bible`，确认后发送 `confirm_bible: true`。",
            meta,
        )

    if payload.get("confirm_bible"):
        session = set_bible(session, session["story_bible"], approved=True)
        session = set_phase(session, PHASE_OUTLINE)
        meta["source"] = "bible_confirmed"
        return session, "故事圣经已锁定。将生成全书章节大纲…", meta

    if payload.get("story_bible_patch") and isinstance(payload["story_bible_patch"], dict):
        from _lib.planning import normalize_story_bible

        merged = normalize_story_bible({
            **(session.get("story_bible") or {}),
            **payload["story_bible_patch"],
        })
        session = set_bible(session, merged, approved=False)
        meta["source"] = "bible_patched"
        return session, "故事圣经已更新。确认后发送 `confirm_bible: true`。", meta

    return session, "等待你确认故事圣经（`confirm_bible: true`）。", meta


def _run_outline(session: dict, payload: dict) -> tuple[dict, str, dict]:
    meta: dict[str, Any] = {"source": "outline"}
    outline = session.get("outline") or {}

    if not outline.get("chapters"):
        chapters, issues = generate_outline(session)
        session = set_outline(session, chapters=chapters, status="draft")
        meta["validation_issues"] = issues
        meta["source"] = "outline_generated"
        return (
            session,
            f"全书大纲已生成（{len(chapters)} 章）。确认后发送 `confirm_outline: true`。",
            meta,
        )

    if payload.get("confirm_outline"):
        session = set_outline(session, status="approved")
        session = dict(session)
        session["outline_approved"] = True
        session = set_phase(session, PHASE_CHAPTER)
        session = set_chapter_work(session, subphase=CHAPTER_PLAN, current_number=1)
        session, plan_reply, pm = _advance_chapter_plan(session)
        meta.update(pm)
        meta["source"] = "outline_confirmed"
        return session, f"章节大纲已确认。{plan_reply}", meta

    return session, "等待你确认章节大纲（`confirm_outline: true`）。", meta


def _advance_chapter_plan(session: dict) -> tuple[dict, str, dict]:
    n = current_chapter_number(session)
    plan, issues = generate_chapter_plan(session, n)
    session = set_chapter_work(session, plan=plan, subphase=CHAPTER_PLAN, draft=None)
    return (
        session,
        f"第 {n} 章计划已生成。审阅 `chapter_work.plan` 后发送 `approve_plan: true` 或 `reject_plan` 附备注。",
        {"source": "chapter_plan_generated", "validation_issues": issues},
    )


def _run_chapter(session: dict, payload: dict) -> tuple[dict, str, dict]:
    sub = chapter_subphase(session)
    n = current_chapter_number(session)
    cw = session.get("chapter_work") or {}
    meta: dict[str, Any] = {"source": f"chapter_{sub}", "chapter_number": n}

    if sub == CHAPTER_PLAN:
        if payload.get("reject_plan"):
            notes = str(payload.get("notes") or payload.get("message") or "")
            if cw.get("plan"):
                plan = dict(cw["plan"])
                plan["approval"] = {"status": "rejected", "user_notes": notes}
                session = set_chapter_work(session, plan=plan)
            session, reply, m = _advance_chapter_plan(session)
            meta.update(m)
            meta["source"] = "chapter_plan_rejected"
            return session, f"已根据反馈重新生成第 {n} 章计划。{reply}", meta

        if payload.get("approve_plan"):
            plan = dict(cw.get("plan") or {})
            notes = str(payload.get("notes") or "")
            plan["approval"] = {"status": "approved", "user_notes": notes}
            session = set_chapter_work(session, plan=plan, subphase=CHAPTER_DRAFT)
            meta["source"] = "chapter_plan_approved"
            return session, f"第 {n} 章计划已批准，开始生成草稿…", meta

        if not cw.get("plan"):
            return _advance_chapter_plan(session)

        return (
            session,
            f"等待你批准第 {n} 章计划（`approve_plan: true`）。",
            meta,
        )

    if sub == CHAPTER_DRAFT:
        plan = cw.get("plan") or {}
        if not cw.get("draft"):
            draft, issues = generate_chapter_draft(session, plan)
            session = set_chapter_work(session, draft=draft, subphase=CHAPTER_CONTINUITY)
            meta["validation_issues"] = issues
            meta["source"] = "chapter_draft_generated"
            return session, f"第 {n} 章草稿已生成，正在进行连续性校验…", meta

        if payload.get("request_revision"):
            notes = str(payload.get("notes") or payload.get("message") or "")
            session = set_chapter_work(
                session,
                draft=None,
                continuity_report=None,
                subphase=CHAPTER_DRAFT,
            )
            draft_new, issues = generate_chapter_draft(session, plan)
            rev = dict(draft_new.get("revision") or {})
            rev["user_notes"] = notes
            rev["version"] = int(rev.get("version") or 1) + 1
            draft_new["revision"] = rev
            session = set_chapter_work(session, draft=draft_new, subphase=CHAPTER_CONTINUITY)
            meta["validation_issues"] = issues
            meta["source"] = "chapter_draft_revised"
            return session, f"已根据批注修订第 {n} 章草稿，继续连续性校验…", meta

        session = set_chapter_work(session, subphase=CHAPTER_CONTINUITY)
        return session, f"第 {n} 章草稿待校验…", meta

    if sub == CHAPTER_CONTINUITY:
        bible = session.get("story_bible") or {}
        plan = cw.get("plan") or {}
        draft = cw.get("draft") or {}
        if not cw.get("continuity_report"):
            report = run_continuity_check(bible, plan, draft)
            session = set_chapter_work(session, continuity_report=report)
            if not report.get("passed"):
                meta["continuity_report"] = report
                meta["source"] = "continuity_failed"
                return (
                    session,
                    f"连续性检查发现 {len(report.get('issues') or [])} 项问题。"
                    f"发送 `accept_draft: true` 仍继续，或 `request_revision` 修订。",
                    meta,
                )
            meta["continuity_report"] = report
            meta["source"] = "continuity_passed"
            return (
                session,
                f"连续性检查通过。{report.get('summary', '')} "
                f"审阅草稿后发送 `accept_draft: true` 回写故事圣经。",
                meta,
            )

        report = cw.get("continuity_report") or {}
        if not payload.get("accept_draft"):
            return (
                session,
                "请审阅草稿与连续性报告。确认后发送 `accept_draft: true`，或 `request_revision` 修订。",
                {**meta, "continuity_report": report},
            )
        session = set_chapter_work(session, subphase=CHAPTER_UPDATE)
        session, reply, meta = _run_chapter(session, payload)
        return session, reply, meta

    if sub == CHAPTER_UPDATE:
        bible = session.get("story_bible") or {}
        plan = cw.get("plan") or {}
        draft = cw.get("draft") or {}
        updated = apply_draft_to_bible(bible, plan, draft)
        session = set_bible(session, updated)

        completed = list(cw.get("completed") or [])
        if n not in completed:
            completed.append(n)
        total = total_chapters(session)

        if n >= total:
            session = set_chapter_work(
                session,
                completed=completed,
                plan=None,
                draft=None,
                continuity_report=None,
            )
            session = set_phase(session, PHASE_COMPLETE)
            meta["source"] = "all_chapters_done"
            return session, f"全书 {total} 章创作完成。", meta

        next_n = n + 1
        session = set_chapter_work(
            session,
            current_number=next_n,
            subphase=CHAPTER_PLAN,
            plan=None,
            draft=None,
            continuity_report=None,
            completed=completed,
        )

        if n % MID_REVIEW_INTERVAL == 0:
            session = set_phase(session, PHASE_MID_REVIEW)
            mr = dict(session.get("mid_review") or {})
            mr["pending"] = True
            mr["last_at_chapter"] = n
            session = dict(session)
            session["mid_review"] = mr
            meta["source"] = "mid_review_triggered"
            return (
                session,
                f"第 {n} 章已回写圣经。已完成 {len(completed)}/{total} 章，进入中段回顾。",
                meta,
            )

        session, reply, m = _advance_chapter_plan(session)
        meta.update(m)
        meta["source"] = "chapter_complete_next"
        return session, f"第 {n} 章已回写圣经。{reply}", meta

    return session, "未知章节子阶段。", meta


def _run_mid_review(session: dict, payload: dict) -> tuple[dict, str, dict]:
    meta: dict[str, Any] = {"source": "mid_review"}
    if not payload.get("confirm_mid_review"):
        n = current_chapter_number(session)
        return (
            session,
            f"中段回顾：请确认人物弧、情节方向是否继续。发送 `confirm_mid_review: true` 进入第 {n} 章。",
            meta,
        )

    mr = dict(session.get("mid_review") or {})
    mr["pending"] = False
    mr["notes"] = str(payload.get("notes") or payload.get("message") or "")
    session = dict(session)
    session["mid_review"] = mr
    session = set_phase(session, PHASE_CHAPTER)
    session, reply, m = _advance_chapter_plan(session)
    meta.update(m)
    meta["source"] = "mid_review_confirmed"
    return session, f"继续创作。{reply}", meta


def _run_phase(session: dict, payload: dict) -> tuple[dict, str, dict]:
    phase = session.get("current_phase") or PHASE_SETUP

    if phase == PHASE_SETUP:
        if not setup_complete(session):
            session, reply, meta = _run_setup(session, payload)
            if not setup_complete(session):
                return session, reply, meta
        session = set_phase(session, PHASE_BIBLE)
        phase = PHASE_BIBLE

    if phase == PHASE_BIBLE:
        session, reply, meta = _run_bible(session, payload)
        if session.get("current_phase") == PHASE_OUTLINE and not (session.get("outline") or {}).get("chapters"):
            session, outline_reply, om = _run_outline(session, payload)
            meta.update(om)
            return session, f"{reply} {outline_reply}", meta
        return session, reply, meta

    if phase == PHASE_OUTLINE:
        return _run_outline(session, payload)

    if phase == PHASE_CHAPTER:
        session, reply, meta = _run_chapter(session, payload)
        while meta.get("source") == "chapter_plan_approved":
            if chapter_subphase(session) == CHAPTER_DRAFT:
                session, reply, meta = _run_chapter(session, payload)
            else:
                break
        while meta.get("source") == "chapter_draft_generated":
            if chapter_subphase(session) == CHAPTER_CONTINUITY:
                session, reply, meta = _run_chapter(session, payload)
            else:
                break
        return session, reply, meta

    if phase == PHASE_MID_REVIEW:
        return _run_mid_review(session, payload)

    if phase == PHASE_COMPLETE:
        return session, "人生剧本创作已完成。", {"source": "complete"}

    return session, "未知阶段。", {"source": "error"}


def run(user_input: str, **kwargs) -> dict:
    payload = _parse_payload(user_input, kwargs)
    begin_turn()

    session = normalize_session(payload.get("session"))
    if payload.get("reset"):
        session = empty_session()

    session = _ingest_handoff(session, payload)
    text = str(payload.get("message") or "").strip()

    session, reply, turn_meta = _run_phase(session, payload)
    llm_calls = drain_calls()
    session = append_llm_calls(session, llm_calls)

    if text:
        session = record_turn(session, text, reply)

    phase = session.get("current_phase") or PHASE_SETUP
    cw = session.get("chapter_work") or {}

    result = {
        "output": _summary(session),
        "reply": reply,
        "session": session,
        "current_phase": phase,
        "phase_label": PHASE_LABELS.get(phase, phase),
        "chapter_subphase": chapter_subphase(session) if phase == PHASE_CHAPTER else None,
        "current_chapter": current_chapter_number(session) if phase == PHASE_CHAPTER else None,
        "story_bible": session.get("story_bible"),
        "outline": session.get("outline"),
        "chapter_plan": cw.get("plan"),
        "chapter_draft": cw.get("draft"),
        "continuity_report": cw.get("continuity_report"),
        "active_question": turn_meta.get("active_question"),
        "llm_calls": llm_calls,
        "meta": {
            "agent": "life-script-author",
            "version": "0.1.0",
            "turn_source": turn_meta.get("source"),
            "llm_available": is_llm_available(),
            "setup_complete": setup_complete(session),
            "bible_approved": session.get("bible_approved"),
            "outline_approved": session.get("outline_approved"),
            "chapters_completed": len(cw.get("completed") or []),
            "chapters_total": total_chapters(session),
            "all_complete": all_chapters_complete(session),
            **{k: v for k, v in turn_meta.items() if k != "active_question"},
        },
    }
    return result


if __name__ == "__main__":
    sample_handoff = {
        "reset": True,
        "handoff": {
            "planning_profile": {
                "anchors": {
                    "goal": "三年内成为独立产品负责人",
                    "current": "前端工程师，刚接手小模块",
                },
            },
            "scenario_set": {
                "selected_scenario_id": "scenario_balanced",
                "scenarios": [{
                    "id": "scenario_balanced",
                    "title": "平衡路径",
                    "tagline": "稳步转型",
                    "premises": [{"text": "利用现有技术信任积累产品能力"}],
                }],
            },
        },
        "skip_setup_questions": True,
        "creative_intent": {
            "narrative_perspective": "第三人称有限视角",
            "time_span": "三年",
            "genre_intensity": "现实主义",
            "ending_openness": "semi_open",
            "taboos": ["真实公司名"],
        },
    }
    raw = sys.argv[1] if len(sys.argv) > 1 else json.dumps(sample_handoff, ensure_ascii=False)
    print(json.dumps(run(raw), ensure_ascii=False, indent=2))
