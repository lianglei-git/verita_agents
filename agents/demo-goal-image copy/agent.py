"""Demo：根据文字描述生成目标意象图（GLM-Image）。"""

from __future__ import annotations

import json
from typing import Any

from _lib.image import ImageConfig, get_image_client, is_image_api_available

DEFAULT_SIZE = "1280x1280"
SIZE_OPTIONS = ("1024x1024", "1280x1280", "768x1344", "1344x768")


def _parse_input(user_input: str) -> dict[str, Any]:
    if not user_input or not user_input.strip():
        return {"prompt": "", "size": DEFAULT_SIZE}
    try:
        data = json.loads(user_input)
        if isinstance(data, dict):
            return {
                "prompt": str(data.get("prompt") or "").strip(),
                "size": str(data.get("size") or DEFAULT_SIZE).strip() or DEFAULT_SIZE,
            }
    except json.JSONDecodeError:
        pass
    return {"prompt": user_input.strip(), "size": DEFAULT_SIZE}


def run(user_input: str, **kwargs) -> dict:
    payload = _parse_input(user_input)
    prompt = payload["prompt"]
    size = payload["size"]

    if not prompt:
        return {
            "output": "",
            "error": "请填写画面描述（prompt）",
            "meta": {"agent": "demo-goal-image", "image_available": is_image_api_available()},
        }

    if size not in SIZE_OPTIONS:
        size = DEFAULT_SIZE

    cfg = ImageConfig.from_overrides(kwargs.get("image_config"))
    client = get_image_client(cfg)
    if client is None:
        return {
            "output": "",
            "error": "未配置图像 API（请设置 IMAGE_API_KEY 或 OPENAI_API_KEY）",
            "prompt": prompt,
            "size": size,
            "meta": {
                "agent": "demo-goal-image",
                "image_available": False,
                "model": cfg.model,
            },
        }

    try:
        image = client.generate(prompt, size=size)
    except RuntimeError as exc:
        return {
            "output": "",
            "error": str(exc),
            "prompt": prompt,
            "size": size,
            "meta": {"agent": "demo-goal-image", "model": cfg.model},
        }

    image_url = image.get("url") or ""
    b64 = image.get("b64_json")
    display_url = image_url
    if not display_url and b64:
        display_url = f"data:image/png;base64,{b64}"

    return {
        "output": display_url,
        "image_url": image_url,
        "prompt": prompt,
        "size": size,
        "content_filter": image.get("content_filter"),
        "meta": {
            "agent": "demo-goal-image",
            "model": cfg.model,
            "image_available": True,
            "created": image.get("created"),
        },
    }


if __name__ == "__main__":
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else '{"prompt":"一只坐在窗台上的小猫"}'
    print(json.dumps(run(text), ensure_ascii=False, indent=2))
