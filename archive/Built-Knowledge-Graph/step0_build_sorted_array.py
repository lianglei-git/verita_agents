"""
Step 0: 合并各等级 full_sort_latest.json → 统一的 A1_C2_sorted.json

数据来源：
  Lab-ConstructingSpiralSyntax/output/<LEVEL>/phase1/full_sort_latest.json
  其中 LEVEL = A1, A2, B1, B2, C1, C2

输出：
  output/A1_C2_sorted.json

数组顺序即为当前阶段唯一可信的默认学习顺序来源。
在每个等级内，按 llm_score 升序排列，忠实保留源文件既定顺序。
"""

import json
import os

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, "..", "Lab-ConstructingSpiralSyntax", "output")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def load_level_json(level: str) -> list:
    """
    加载单个等级的 full_sort_latest.json，返回该等级的 grammar point 列表。
    列表已按 llm_score 升序排列（源文件就是排序后的结果）。
    """
    path = os.path.join(SOURCE_DIR, level, "phase1", "full_sort_latest.json")
    if not os.path.exists(path):
        print(f"  [WARN] 未找到 {level} 的数据文件: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_items = data.get("items", [])
    if not raw_items:
        print(f"  [WARN] {level} 数据文件 items 为空")
        return []

    result = []
    for item in raw_items:
        info = item.get("egp_info", {})
        gp = {
            "egp_id": item.get("egp_id", ""),
            "level": level,
            "llm_score": item.get("llm_score"),
            "score_reason": item.get("score_reason", ""),
            "super_category": _parse_super_category(info.get("category", "")),
            "sub_category": _parse_sub_category(info.get("category", "")),
            "name_zh": info.get("chinese_human_name", ""),
            "guideword": _parse_guideword(info.get("content", "")),
            "can_do": _parse_can_do(info.get("content", info.get("can_do", ""))),
            "examples": _split_field(info.get("examples", "")),
            "trigger_lemmas": _split_field(info.get("trigger_lemmas", "")),
            "keywords": _split_keywords(info.get("keywords", "")),
            "chinese_doc": info.get("chinese_doc", ""),
            "core_rules": info.get("core_rules", ""),
            "common_errors": info.get("common_errors", ""),
        }
        result.append(gp)

    return result


def _parse_super_category(raw: str) -> str:
    import re
    m = re.search(r"SuperCategory:\s*(.+?)(?:\.\s*SubCategory:|$)", raw)
    return m.group(1).strip() if m else ""


def _parse_sub_category(raw: str) -> str:
    import re
    m = re.search(r"SubCategory:\s*(.+)", raw)
    return m.group(1).strip() if m else ""


def _parse_guideword(content: str) -> str:
    import re
    m = re.search(r"Guideword:\s*(.+?)(?:\.\s*CanDo:|$)", content)
    if m:
        return m.group(1).strip().rstrip(".")
    return ""


def _parse_can_do(content: str) -> str:
    import re
    m = re.search(r"CanDo:\s*(.+)", content)
    if m:
        return m.group(1).strip()
    return content.strip()


def _split_field(raw: str) -> list:
    if not raw or not raw.strip():
        return []
    return [item.strip() for item in raw.split("、") if item.strip()]


def _split_keywords(raw: str) -> list:
    if not raw or not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_sorted_array() -> list:
    """
    按 A1→A2→B1→B2→C1→C2 顺序拼接各等级数据。
    每个等级内部保持源文件的 llm_score 升序，即 LLM 给出的最优学习顺序。
    """
    all_items = []
    stats = {}

    for level in LEVELS:
        items = load_level_json(level)
        stats[level] = len(items)
        all_items.extend(items)

    return all_items, stats


def save_sorted_array(items: list):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, "A1_C2_sorted.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return filepath


def main():
    print("=" * 60)
    print("  Step 0: 合并各等级语法点 → A1_C2_sorted.json")
    print("=" * 60)

    items, stats = build_sorted_array()

    print("\n  各等级语法点数量:")
    for level in LEVELS:
        print(f"    {level}: {stats.get(level, 0)}")
    print(f"\n  合计: {len(items)} 个语法点")

    if not items:
        print("\n  [ERROR] 未加载到任何数据，请检查路径配置")
        return

    filepath = save_sorted_array(items)
    print(f"\n  已生成: {filepath}")

    # 简单质量检查
    ids = [gp["egp_id"] for gp in items]
    dup = [x for x in set(ids) if ids.count(x) > 1]
    if dup:
        print(f"  [WARN] 发现重复 egp_id ({len(dup)} 个): {dup[:5]}")
    else:
        print(f"  egp_id 无重复，数据干净")

    missing_level = [gp["egp_id"] for gp in items if not gp["level"]]
    if missing_level:
        print(f"  [WARN] {len(missing_level)} 个语法点缺少 level 字段")

    print("\n  前 3 条预览:")
    for gp in items[:3]:
        print(f"    [{gp['level']}] {gp['egp_id']} {gp['name_zh'][:30]}"
              f" ({gp['super_category']} > {gp['sub_category']})")


if __name__ == "__main__":
    main()
