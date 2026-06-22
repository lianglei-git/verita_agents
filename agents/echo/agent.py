"""Echo agent — Views 接入示例"""

from __future__ import annotations


def run(user_input: str, **kwargs) -> dict:
    return {
        "output": f"[echo] {user_input}",
        "meta": {"agent": "echo", "received_kwargs": list(kwargs.keys())},
    }


if __name__ == "__main__":
    import json
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else "hello"
    print(json.dumps(run(text), ensure_ascii=False, indent=2))
