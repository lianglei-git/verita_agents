"""Life Script Author — 阶段常量与标签。"""

from __future__ import annotations

# 主阶段
PHASE_SETUP = "setup"
PHASE_BIBLE = "bible"
PHASE_OUTLINE = "outline"
PHASE_CHAPTER = "chapter"
PHASE_MID_REVIEW = "mid_review"
PHASE_COMPLETE = "complete"

PHASE_LABELS: dict[str, str] = {
    PHASE_SETUP: "创作意图确认",
    PHASE_BIBLE: "故事圣经",
    PHASE_OUTLINE: "章节大纲",
    PHASE_CHAPTER: "逐章创作",
    PHASE_MID_REVIEW: "中段回顾",
    PHASE_COMPLETE: "创作完成",
}

# 章节子阶段
CHAPTER_PLAN = "plan"
CHAPTER_DRAFT = "draft"
CHAPTER_CONTINUITY = "continuity"
CHAPTER_UPDATE = "update"

CHAPTER_SUB_LABELS: dict[str, str] = {
    CHAPTER_PLAN: "章节计划",
    CHAPTER_DRAFT: "章节草稿",
    CHAPTER_CONTINUITY: "连续性校验",
    CHAPTER_UPDATE: "圣经回写",
}

DEFAULT_CHAPTER_COUNT = 36
MID_REVIEW_INTERVAL = 4
TARGET_WORD_MIN = 2500
TARGET_WORD_MAX = 3500

ADAPTATION_MODES = ("faithful", "deidentified", "fictionalized")
DEFAULT_ADAPTATION_MODE = "deidentified"
