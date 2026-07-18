"""规划与叙事 Agent 的安全提示词约束与轻量校验。"""

from __future__ import annotations

import re
from typing import Any, Literal

from .types import ClaimKind

PlanningScope = Literal["planning", "narrative", "gap", "scenario", "roadmap"]

# --- 系统提示词块 ---

PLANNING_SAFETY_RULES = """\
## 安全与可靠性约束（必须遵守）

1. **区分信息类型**：每条关键陈述必须标注为以下之一：
   - `fact`：用户明确自述、可引用的事实
   - `assumption`：为补全规划而做的显式假设（须说明依据，不得伪装成用户事实）
   - `uncertainty`：当前无法判断、需要用户确认或后续验证的未知项

2. **禁止确定性人生预测**：不得输出「你一定会…」「命中注定」「必然成功/失败」等命运式结论。
   情景推演是**互斥假设路径**的比较，不是对未来的预言。

3. **禁止心理/医疗诊断**：不得对用户做精神疾病、人格障碍、创伤后应激等临床诊断，
   不得给出用药或治疗建议。可讨论压力、动力、习惯等自述层面的非临床话题。

4. **禁止伪造精确数据**：无法从用户自述推断时，不得编造具体收入、年龄节点、录取概率、
   IQ/人格类型等精确数值或标签。

5. **高影响假设须确认**：对路线选择有显著影响的低置信度假设，标记 `requires_confirmation: true`，
   在定稿前提示用户确认或修正。

6. **可追溯性**：建议、差距、情景与行动项应能关联到用户事实或显式假设（`evidence_refs`）。
"""

NARRATIVE_SAFETY_RULES = """\
## 叙事创作安全约束（必须遵守）

1. 正文与设定须标明为基于用户选择情景创作的**虚构叙事**（「如果……会如何」），不是现实预测。
2. 默认采用**去识别化改编**：不把用户真实姓名、住址、雇主、可识别关系直接写入正文。
3. 心理健康、创伤、现实关系仅可作为用户**主动确认**的创作素材，不得以画像推断补全。
4. 遵守用户在 `taboos` / `do_not_identify` 中声明的禁区。
5. 连续性检查应**报告**矛盾，不得静默掩盖时间线、人物动机或信息差错误。
"""

SCOPE_RULES: dict[PlanningScope, str] = {
    "planning": PLANNING_SAFETY_RULES,
    "gap": PLANNING_SAFETY_RULES,
    "scenario": PLANNING_SAFETY_RULES + "\n情景输出须强调可比较、可逆，而非单一正确答案。",
    "roadmap": PLANNING_SAFETY_RULES + "\n路线图阶段须含可验证里程碑与未达标时的调整分支。",
    "narrative": PLANNING_SAFETY_RULES + "\n" + NARRATIVE_SAFETY_RULES,
}

OUTPUT_FORMAT_REMINDER = """\
## 输出格式

- 返回合法 JSON 对象，符合给定 schema。
- 使用 `attributed_claim` 结构承载事实/假设/不确定性，不要把模型推断写入 `stated_facts`。
- 中文输出，语气务实、可执行，避免空洞励志。
"""

# --- 禁止表述（轻量启发式，供 Agent 后置校验）---

_FORBIDDEN_DETERMINISTIC = re.compile(
    r"你一定会|你必然|命中注定|注定会|算命|预言|八字|星盘|"
    r"百分之百成功|必然成功|必然失败|铁定会|肯定会成功",
    re.I,
)

_FORBIDDEN_DIAGNOSIS = re.compile(
    r"患有(抑郁症|焦虑症|双相|精神分裂|人格障碍|创伤后应激|"
    r"注意力缺陷|自闭症|强迫症)|"
    r"诊断为|临床诊断|精神障碍|心理疾病患者|"
    r"你应该(服药|看心理医生|接受心理治疗)",
    re.I,
)

_FORBIDDEN_PRECISE_GUESS = re.compile(
    r"(MBTI|九型人格|大五人格).{0,8}(是|为)\s*[A-Z0-9]{2,5}|"
    r"年收入(约|大约|至少)\s*\d+万|"
    r"录取概率\s*\d{1,3}%|"
    r"智商\s*\d{2,3}",
    re.I,
)


def build_safety_system_prompt(scope: PlanningScope = "planning") -> str:
    """拼装可注入 LLM system 的安全约束块。"""
    rules = SCOPE_RULES.get(scope, PLANNING_SAFETY_RULES)
    return f"{rules}\n{OUTPUT_FORMAT_REMINDER}"


def scan_text_violations(text: str) -> list[dict[str, str]]:
    """扫描自由文本中的潜在安全违规（启发式，非完备）。"""
    if not text or not text.strip():
        return []
    violations: list[dict[str, str]] = []
    if _FORBIDDEN_DETERMINISTIC.search(text):
        violations.append({
            "code": "deterministic_prediction",
            "message": "含确定性命运/成功预言表述",
        })
    if _FORBIDDEN_DIAGNOSIS.search(text):
        violations.append({
            "code": "psychological_diagnosis",
            "message": "含心理/医疗诊断或治疗建议表述",
        })
    if _FORBIDDEN_PRECISE_GUESS.search(text):
        violations.append({
            "code": "fabricated_precision",
            "message": "含可能伪造的精确人格/收入/概率数据",
        })
    return violations


def validate_claim_kind_source(kind: str, source: str) -> list[str]:
    """校验归因声明的 kind/source 组合是否合理。"""
    issues: list[str] = []
    valid_kinds = {"fact", "assumption", "uncertainty"}
    valid_sources = {"user_stated", "user_inferred", "model_assumed", "model_inferred"}
    if kind not in valid_kinds:
        issues.append(f"invalid claim kind: {kind}")
    if source not in valid_sources:
        issues.append(f"invalid claim source: {source}")
    if kind == "fact" and source.startswith("model_"):
        issues.append("fact must not use model_* source")
    if kind == "assumption" and source == "user_stated":
        issues.append("assumption should not use user_stated source")
    return issues


def audit_attributed_claim(claim: dict[str, Any]) -> list[str]:
    """审计单条 attributed_claim。"""
    issues = validate_claim_kind_source(
        str(claim.get("kind") or ""),
        str(claim.get("source") or ""),
    )
    text = str(claim.get("text") or "")
    for v in scan_text_violations(text):
        issues.append(f"{v['code']}: {v['message']}")
    conf = claim.get("confidence")
    if conf is not None:
        try:
            c = float(conf)
            if not 0 <= c <= 1:
                issues.append("confidence must be between 0 and 1")
        except (TypeError, ValueError):
            issues.append("confidence must be numeric")
    if claim.get("requires_confirmation") and str(claim.get("kind")) == "fact":
        issues.append("requires_confirmation should not apply to fact")
    return issues


def audit_document_text_fields(payload: dict[str, Any], fields: list[str]) -> list[str]:
    """对契约中若干文本字段做安全扫描，返回问题描述列表。"""
    issues: list[str] = []
    for field in fields:
        val = payload.get(field)
        if isinstance(val, str):
            for v in scan_text_violations(val):
                issues.append(f"{field}: {v['message']}")
    return issues


def split_claims_by_kind(
    claims: list[dict[str, Any]],
) -> dict[ClaimKind, list[dict[str, Any]]]:
    """按 kind 分组 attributed_claim 列表。"""
    buckets: dict[ClaimKind, list[dict[str, Any]]] = {
        "fact": [],
        "assumption": [],
        "uncertainty": [],
    }
    for item in claims:
        kind = str(item.get("kind") or "assumption")
        if kind not in buckets:
            kind = "assumption"
        buckets[kind].append(item)  # type: ignore[index]
    return buckets


def is_model_inference(source: str) -> bool:
    return source in ("model_assumed", "model_inferred")
