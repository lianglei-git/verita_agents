"""
Step 2: 解析 EGP 数据

正式数据链路（来自需求文档 §5）：
  step0 生成的 output/A1_C2_sorted.json → GrammarPointData 列表

兼容链路（过渡，将来废弃）：
  egp_all.csv → parse_egp_csv()

默认使用 A1_C2_sorted.json。
如需使用 CSV 兼容链路，显式调用 parse_egp_csv()。
"""

import csv
import json
import os
import re
from dataclasses import dataclass, field

SORTED_JSON_PATH = os.path.join(
    os.path.dirname(__file__), "output", "A1_C2_sorted.json"
)

CSV_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "资源数据", "dirty", "egp_all.csv"
)


@dataclass
class GrammarPointData:
    """单条语法点数据"""
    egp_id: str
    level: str
    super_category: str
    sub_category: str
    name_zh: str
    guideword: str
    can_do: str
    examples: list = field(default_factory=list)
    trigger_lemmas: list = field(default_factory=list)
    keywords: list = field(default_factory=list)
    chinese_doc: str = ""
    core_rules: str = ""
    common_errors: str = ""
    llm_score: float = None
    score_reason: str = ""

    @property
    def content(self) -> str:
        parts = []
        if self.guideword:
            parts.append(f"Guideword: {self.guideword}")
        if self.can_do:
            parts.append(f"CanDo: {self.can_do}")
        return ". ".join(parts)


# ─────────────────────────────────────────────────────────────
# 正式链路：从 A1_C2_sorted.json 解析
# ─────────────────────────────────────────────────────────────

def parse_egp_sorted(json_path: str = None) -> list:
    """
    从 step0 生成的 A1_C2_sorted.json 解析，返回 GrammarPointData 列表。
    顺序即为权威学习顺序（A1→C2，每等级内按 llm_score 升序）。
    """
    if json_path is None:
        json_path = SORTED_JSON_PATH

    json_path = os.path.abspath(json_path)
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"A1_C2_sorted.json 未找到: {json_path}\n"
            f"请先运行 step0_build_sorted_array.py"
        )

    with open(json_path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    results = []
    for item in raw_items:
        gp = GrammarPointData(
            egp_id=item.get("egp_id", "").strip(),
            level=item.get("level", "").strip(),
            super_category=item.get("super_category", "").strip(),
            sub_category=item.get("sub_category", "").strip(),
            name_zh=item.get("name_zh", "").strip(),
            guideword=item.get("guideword", "").strip(),
            can_do=item.get("can_do", "").strip(),
            examples=item.get("examples", []),
            trigger_lemmas=item.get("trigger_lemmas", []),
            keywords=item.get("keywords", []),
            chinese_doc=item.get("chinese_doc", "").strip(),
            core_rules=item.get("core_rules", "").strip(),
            common_errors=item.get("common_errors", "").strip(),
            llm_score=item.get("llm_score"),
            score_reason=item.get("score_reason", "").strip(),
        )
        results.append(gp)

    return results


# ─────────────────────────────────────────────────────────────
# 兼容链路：从 CSV 解析（过渡用，将来废弃）
# ─────────────────────────────────────────────────────────────

def _parse_category(raw: str):
    super_cat = ""
    sub_cat = ""
    m_super = re.search(r"SuperCategory:\s*(.+?)(?:\.\s*SubCategory:|$)", raw)
    if m_super:
        super_cat = m_super.group(1).strip()
    m_sub = re.search(r"SubCategory:\s*(.+)", raw)
    if m_sub:
        sub_cat = m_sub.group(1).strip()
    return super_cat, sub_cat


def _parse_content(raw: str):
    guideword = ""
    can_do = ""
    m_gw = re.search(r"Guideword:\s*(.+?)(?:\.\s*CanDo:|$)", raw)
    if m_gw:
        guideword = m_gw.group(1).strip().rstrip(".")
    m_cd = re.search(r"CanDo:\s*(.+)", raw)
    if m_cd:
        can_do = m_cd.group(1).strip()
    return guideword, can_do


def _split_field(raw: str) -> list:
    if not raw or not raw.strip():
        return []
    return [item.strip() for item in raw.split("、") if item.strip()]


def _split_keywords(raw: str) -> list:
    if not raw or not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_egp_csv(csv_path: str = None) -> list:
    """
    [兼容链路，将来废弃] 从 egp_all.csv 解析，返回 GrammarPointData 列表。
    """
    if csv_path is None:
        csv_path = CSV_PATH

    csv_path = os.path.abspath(csv_path)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"EGP CSV not found: {csv_path}")

    results = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            super_cat, sub_cat = _parse_category(row.get("category", ""))
            guideword, can_do = _parse_content(row.get("content", ""))
            gp = GrammarPointData(
                egp_id=row.get("egp_id", "").strip(),
                level=row.get("level", "").strip(),
                super_category=super_cat,
                sub_category=sub_cat,
                name_zh=row.get("chinese_human_name", "").strip(),
                guideword=guideword,
                can_do=can_do,
                examples=_split_field(row.get("examples", "")),
                trigger_lemmas=_split_field(row.get("trigger_lemmas", "")),
                keywords=_split_keywords(row.get("keywords", "")),
                chinese_doc=row.get("chinese_doc", "").strip(),
                core_rules=row.get("core_rules", "").strip(),
                common_errors=row.get("common_errors", "").strip(),
            )
            results.append(gp)

    return results


# ─────────────────────────────────────────────────────────────
# 默认入口：优先使用正式链路
# ─────────────────────────────────────────────────────────────

def load_grammar_points() -> list:
    """
    优先从 A1_C2_sorted.json 加载；若不存在则尝试 CSV 兼容链路。
    """
    if os.path.exists(os.path.abspath(SORTED_JSON_PATH)):
        return parse_egp_sorted()

    print("  [兼容模式] A1_C2_sorted.json 不存在，退回 CSV 链路（建议运行 step0）")
    return parse_egp_csv()


# ─────────────────────────────────────────────────────────────
# 统计
# ─────────────────────────────────────────────────────────────

def print_parse_stats(data: list):
    from collections import Counter
    print("=" * 60)
    print("  EGP 数据解析完成")
    print("=" * 60)
    print(f"\n  总语法点: {len(data)}")

    level_counts = Counter(gp.level for gp in data)
    print("\n  按等级分布:")
    from step1_ontology import LEVELS
    for lvl in LEVELS:
        print(f"    {lvl}: {level_counts.get(lvl, 0)}")

    super_counts = Counter(gp.super_category for gp in data)
    print(f"\n  语法大类 ({len(super_counts)}):")
    for cat, cnt in super_counts.most_common():
        print(f"    {cat:30s}: {cnt}")

    sub_cats = set((gp.super_category, gp.sub_category) for gp in data)
    print(f"\n  语法子类: {len(sub_cats)}")

    has_examples = sum(1 for gp in data if gp.examples)
    total_examples = sum(len(gp.examples) for gp in data)
    print(f"\n  有例句的语法点: {has_examples}/{len(data)} (共 {total_examples} 条)")


if __name__ == "__main__":
    data = load_grammar_points()
    print_parse_stats(data)

    print("\n" + "─" * 60)
    print("  数据示例（前 3 条）:")
    print("─" * 60)
    for gp in data[:3]:
        print(f"\n  [{gp.egp_id}] {gp.name_zh[:30]}")
        print(f"    Level: {gp.level}")
        print(f"    Category: {gp.super_category} > {gp.sub_category}")
        print(f"    CanDo: {gp.can_do[:80]}...")
        print(f"    Examples: {len(gp.examples)} 条")
        print(f"    llm_score: {gp.llm_score}")
