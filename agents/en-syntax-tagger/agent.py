"""英文句法全量标记 — v1学术 / v2教学 / v3 JSON 数据。"""

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

from ls_output import (  # noqa: E402
    normalize_ls_kwargs,
    to_bcp47,
    to_sentence_analyze_output,
)
from versions.registry import (  # noqa: E402
    DEFAULT_VERSION,
    SUPPORTED_VERSIONS,
    get_handler,
    list_versions,
    resolve_api_version,
)

AGENT_ID = "en-syntax-tagger"
PACKAGE_VERSION = "3.0.0"

try:
    import jsonschema
except ImportError:
    jsonschema = None


def _load_schema(api_version: str, kind: str) -> dict[str, Any] | None:
    path = _AGENT_DIR / "versions" / api_version / f"{kind}.schema.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_input(api_version: str, payload: dict[str, Any]) -> list[str]:
    if jsonschema is None:
        return []
    schema = _load_schema(api_version, "input")
    if not schema:
        return []
    try:
        jsonschema.validate(instance=payload, schema=schema)
        return []
    except jsonschema.ValidationError as e:
        return [e.message]


def _validate_ls_output(payload: dict[str, Any]) -> list[str]:
    if jsonschema is None:
        return []
    path = _AGENT_DIR / "ls.output.schema.json"
    if not path.is_file():
        return []
    schema = json.loads(path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=payload, schema=schema)
        return []
    except jsonschema.ValidationError as e:
        return [e.message]


def run(user_input: str, **kwargs: Any) -> dict[str, Any]:
    """
    kwargs:
      - version / api_version: v1 | v2 | v3
        aliases: a/academic→v1, b/teaching→v2, c/json→v3
      - native_lang / learn_lang: 工作台中文名
      - text / learning_language / support_language / user_level / goal / profile: LS
    """
    ls_kwargs = normalize_ls_kwargs(user_input, kwargs)
    sentence = ls_kwargs.get("sentence") or user_input
    requested = kwargs.get("version") or kwargs.get("api_version") or ls_kwargs.get("version")
    api_version = resolve_api_version(
        None if requested is None else str(requested),
        **ls_kwargs,
    )
    skip = {
        "version",
        "api_version",
        "text",
        "learning_language",
        "support_language",
        "user_level",
        "goal",
        "profile",
    }
    handler_kwargs = {k: v for k, v in ls_kwargs.items() if k not in skip}

    handler = get_handler(api_version)

    if hasattr(handler, "normalize_input"):
        normalized = handler.normalize_input(sentence, **handler_kwargs)
        verrs = _validate_input(api_version, normalized)
        if verrs and normalized.get("sentence"):
            return {
                "input": normalized.get("sentence") or "",
                "api_version": api_version,
                "analysis": {},
                "spacy_tokens": [],
                "error": "invalid_input",
                "message": "; ".join(verrs),
                "meta": {
                    "agent": AGENT_ID,
                    "package_version": PACKAGE_VERSION,
                    "api_version": api_version,
                    "validation_errors": verrs,
                },
            }

    result = handler.run(sentence, **handler_kwargs)
    if not isinstance(result, dict):
        return {
            "error": "invalid_handler_result",
            "message": "Handler did not return a dict.",
            "api_version": api_version,
            "meta": {
                "agent": AGENT_ID,
                "package_version": PACKAGE_VERSION,
                "api_version": api_version,
            },
        }

    result.setdefault("api_version", api_version)
    meta = result.setdefault("meta", {})
    meta["agent"] = AGENT_ID
    meta["package_version"] = PACKAGE_VERSION
    meta["api_version"] = api_version

    if requested is not None:
        raw = str(requested).strip().lower()
        resolved_from_raw = resolve_api_version(raw)
        # If caller passed an unknown id, resolver returns default — record fallback
        known = set(SUPPORTED_VERSIONS) | {
            "a", "academic", "b", "teaching", "c", "json", "json_data",
            "1", "2", "3",
        }
        if raw not in known and not (raw.startswith("v") and raw in SUPPORTED_VERSIONS):
            meta["requested_version"] = str(requested)
            meta["version_fallback"] = resolved_from_raw

    learning = kwargs.get("learning_language") or ls_kwargs.get("learn_lang")
    support = kwargs.get("support_language") or ls_kwargs.get("native_lang")
    profile = str(kwargs.get("profile") or meta.get("profile") or "academic")
    if api_version == "v1":
        ls_out = to_sentence_analyze_output(
            result,
            learning_language=to_bcp47(learning, "en"),
            support_language=to_bcp47(support, "zh-CN"),
            profile=profile,
            user_level=str(kwargs["user_level"]) if kwargs.get("user_level") else None,
            goal=str(kwargs["goal"]) if kwargs.get("goal") else None,
        )
        ls_out.get("meta", {}).pop("activity_id", None)
        verrs = _validate_ls_output(ls_out)
        if verrs:
            result["error"] = result.get("error") or "invalid_ls_output"
            result["message"] = result.get("message") or "; ".join(verrs)
            meta["ls_validation_errors"] = verrs
        result["output"] = ls_out

    return result


def main() -> None:
    args = sys.argv[1:]
    version = DEFAULT_VERSION
    if args and args[0] in ("--version", "-V") and len(args) >= 2:
        version = args[1]
        args = args[2:]
    if not args:
        print("Usage: python agent.py [--version v1|v2|v3] '<English sentence>'")
        print("API versions:", json.dumps(list_versions(), ensure_ascii=False, indent=2))
        sys.exit(1)
    print(json.dumps(run(args[0], version=version), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
