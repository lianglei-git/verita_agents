"""路线规划 Agent — 根据用户画像/目标推荐成长路线（demo）。"""

from __future__ import annotations

import json
from typing import Any

from routes import DEFAULT_ROUTE_ID, ROUTES


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
    return {"goal_text": user_input}


def _goal_text(payload: dict) -> str:
    twin = payload.get("twin") or {}
    growth = twin.get("growth") or {}
    ident = twin.get("identity") or {}
    parts = [
        growth.get("goal", ""),
        ident.get("occupation", ""),
        payload.get("goal", ""),
        payload.get("goal_text", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def _score_route(route: dict, text: str) -> int:
    score = 0
    for kw in route.get("keywords", []):
        if kw.lower() in text:
            score += 2
    return score


def _pick_route(payload: dict) -> dict:
    preferred = payload.get("route_id")
    if preferred:
        for route in ROUTES:
            if route["id"] == preferred:
                return route

    text = _goal_text(payload)
    if not text.strip():
        return next(r for r in ROUTES if r["id"] == DEFAULT_ROUTE_ID)

    ranked = sorted(ROUTES, key=lambda r: _score_route(r, text), reverse=True)
    if ranked[0] and _score_route(ranked[0], text) > 0:
        return ranked[0]
    return next(r for r in ROUTES if r["id"] == DEFAULT_ROUTE_ID)


def _build_plan(route: dict, payload: dict) -> dict:
    twin = payload.get("twin") or {}
    goal = (twin.get("growth") or {}).get("goal") or payload.get("goal") or payload.get("goal_text") or ""
    occ = (twin.get("identity") or {}).get("occupation") or payload.get("occupation") or "学习者"

    return {
        "route_id": route["id"],
        "route_name": route["name"],
        "tagline": route["tagline"],
        "description": route["description"],
        "primary_track": route["primary_track"],
        "stages": route["stages"],
        "rationale": f"基于目标「{goal or '未明确'}」与身份「{occ}」，推荐走 {route['name']}。",
        "next_agent": "story-scenario",
    }


def run(user_input: str, **kwargs) -> dict:
    payload = _parse_payload(user_input, kwargs)
    route = _pick_route(payload)
    plan = _build_plan(route, payload)

    # 供下游 story-scenario 使用的简要输出
    stage_titles = " → ".join(s["title"] for s in route["stages"])
    output = f"推荐路线：{route['name']}（{stage_titles}）"

    return {
        "output": output,
        "plan": plan,
        "alternatives": [
            {"id": r["id"], "name": r["name"], "tagline": r["tagline"]}
            for r in ROUTES
            if r["id"] != route["id"]
        ],
        "meta": {"agent": "route-planner", "version": "0.1.0"},
    }


if __name__ == "__main__":
    import sys

    sample = {
        "twin": {
            "identity": {"occupation": "前端工程师"},
            "growth": {"goal": "海外技术面试"},
        }
    }
    raw = sys.argv[1] if len(sys.argv) > 1 else json.dumps(sample, ensure_ascii=False)
    print(json.dumps(run(raw), ensure_ascii=False, indent=2))
