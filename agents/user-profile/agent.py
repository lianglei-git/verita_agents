"""用户画像 Agent — MVP 占位实现"""

from __future__ import annotations

import json


def _parse_input(user_input: str, kwargs: dict) -> dict:
    if kwargs:
        return {
            "career": kwargs.get("career", ""),
            "level": kwargs.get("level", ""),
            "goal": kwargs.get("goal", ""),
            "preference": kwargs.get("preference", ""),
            "fear": kwargs.get("fear", ""),
        }
    if not user_input.strip():
        return {}
    try:
        data = json.loads(user_input)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"goal": user_input}


def run(user_input: str, **kwargs) -> dict:
    data = _parse_input(user_input, kwargs)
    career = data.get("career", "").strip() or "未填写"
    level = data.get("level", "").strip() or "未评估"
    goal = data.get("goal", "").strip() or "未明确"
    preference = data.get("preference", "").strip() or "未说明"
    fear = data.get("fear", "").strip() or "未说明"

    persona_title = f"{career} · 目标：{goal[:24]}"
    summary = (
        f"当前水平：{level}。偏好 {preference}。"
        f"最需突破的场景：{fear}。"
    )
    gaps = [
        f"口语场景应对（关联：{fear}）",
        "技术表达与项目叙述",
        f"与目标「{goal}」匹配的语言功能",
    ]

    return {
        "output": summary,
        "profile": {
            "persona_title": persona_title,
            "summary": summary,
            "gaps": gaps,
            "raw_input": data,
        },
        "meta": {"agent": "user-profile", "version": "0.1.0"},
    }


if __name__ == "__main__":
    import sys

    sample = json.dumps(
        {
            "career": "前端工程师",
            "level": "B1",
            "goal": "海外技术面试",
            "preference": "场景化",
            "fear": "视频会议听不懂",
        },
        ensure_ascii=False,
    )
    text = sys.argv[1] if len(sys.argv) > 1 else sample
    print(json.dumps(run(text), ensure_ascii=False, indent=2))
