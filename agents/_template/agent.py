"""Agent 入口模板 — 复制到 agents/{your-id}/agent.py 并实现 run()"""

from __future__ import annotations


def run(user_input: str, **kwargs) -> dict:
    """
    统一入口。Views 通过 HTTP 调用时会传入：
      - user_input: 字符串主输入（或上游 output 序列化）
      - kwargs: config.json / 前端 options 中的扩展字段

    返回 dict，建议至少包含 output 字段。
    """
    return {
        "output": user_input,
        "meta": {"agent": "__template__"},
    }


if __name__ == "__main__":
    import json
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else "hello"
    print(json.dumps(run(text), ensure_ascii=False, indent=2))
