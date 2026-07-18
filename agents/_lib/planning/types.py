"""规划流水线共享类型与枚举常量。"""

from __future__ import annotations

from typing import Literal

SCHEMA_VERSION = "1.0"

# --- 归因声明 ---
ClaimKind = Literal["fact", "assumption", "uncertainty"]
ClaimSource = Literal["user_stated", "user_inferred", "model_assumed", "model_inferred"]

# --- PlanningProfile ---
Clarity = Literal["low", "medium", "high"]
ReadinessStatus = Literal["collecting", "conditional", "ready"]
GoalPriority = Literal["primary", "secondary"]

# --- GapDiagnosis ---
GapCategory = Literal[
    "skill", "resource", "time", "credential", "network", "mindset", "other"
]
GapPriority = Literal["blocking", "important", "optional"]
GapStatus = Literal["open", "partial", "closed"]

# --- ScenarioSet ---
ScenarioArchetype = Literal["conservative", "balanced", "aggressive"]

# --- StoryBible ---
AdaptationMode = Literal["faithful", "deidentified", "fictionalized"]
EndingOpenness = Literal["open", "semi_open", "closed"]
ForeshadowStatus = Literal["planted", "resolved", "abandoned"]

# --- ChapterPlan / ChapterDraft ---
ApprovalStatus = Literal["draft", "approved", "rejected"]
DraftStatus = Literal["draft", "review", "accepted"]

SCENARIO_ARCHETYPES: tuple[ScenarioArchetype, ...] = (
    "conservative",
    "balanced",
    "aggressive",
)
