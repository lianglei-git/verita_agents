"""统一规划入口 — PRD v2。"""

from __future__ import annotations

from flow import plan_collection_v2


def plan_collection(universal: dict, collection: dict) -> dict:
    return plan_collection_v2(universal, collection)
