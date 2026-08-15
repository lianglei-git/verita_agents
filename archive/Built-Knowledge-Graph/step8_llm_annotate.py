"""
Step 8: LLM 标注跨子类前置依赖

使用 LLM 分析每个语法点，推导出跨 SubCategory 的 PREREQUISITE 关系。

流程：
  1. 加载所有语法点，按等级和子类分组
  2. 为每批语法点构建 prompt：
     - 目标：当前批次的语法点
     - 候选：来自其他子类、等级 ≤ 当前等级的语法点
  3. 调用 LLM API 获取跨类依赖
  4. 解析结果并增量保存
  5. 支持断点续传

使用 Kimi (Moonshot) API，兼容 OpenAI SDK。

运行:
  python step8_llm_annotate.py               # 执行标注
  python step8_llm_annotate.py --dry-run     # 仅预览，不调用 API
  python step8_llm_annotate.py --resume      # 断点续传
"""

import json
import os
import sys
import time
from collections import defaultdict

import yaml

from step1_ontology import LEVELS
from step2_parse_egp import parse_egp_csv

# ============================================================
# 配置加载
# ============================================================

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_client(config):
    """创建 OpenAI 兼容客户端"""
    try:
        from openai import OpenAI
    except ImportError:
        print("  错误: 请先安装 openai 包: pip install openai")
        sys.exit(1)

    api_cfg = config["api"]
    if api_cfg["api_key"] == "YOUR_API_KEY_HERE":
        print("  错误: 请在 config.yaml 中配置你的 API Key")
        sys.exit(1)

    return OpenAI(
        api_key=api_cfg["api_key"],
        base_url=api_cfg["base_url"],
    )


# ============================================================
# 数据准备
# ============================================================

def prepare_data():
    """
    准备标注数据。
    返回:
      - gp_by_id: {egp_id: GrammarPointData}
      - gp_by_sub: {(super_cat, sub_cat): [GrammarPointData]}
      - gp_by_level: {level: [GrammarPointData]}
      - candidate_text: 所有语法点的精简文本（供 prompt 使用）
    """
    data = parse_egp_csv()

    gp_by_id = {gp.egp_id: gp for gp in data}
    gp_by_sub = defaultdict(list)
    gp_by_level = defaultdict(list)

    for gp in data:
        gp_by_sub[(gp.super_category, gp.sub_category)].append(gp)
        gp_by_level[gp.level].append(gp)

    return gp_by_id, gp_by_sub, gp_by_level, data


def build_candidate_text(data, max_level_rank):
    """
    构建候选前置语法点的精简列表文本。
    只包含等级 ≤ max_level_rank 的语法点。
    """
    level_rank = {lvl: i for i, lvl in enumerate(LEVELS)}
    lines = []
    current_cat = ""

    sorted_data = sorted(data, key=lambda g: (
        g.super_category, g.sub_category,
        level_rank.get(g.level, 99), g.egp_id
    ))

    for gp in sorted_data:
        if level_rank.get(gp.level, 99) > max_level_rank:
            continue
        cat_key = f"{gp.super_category} > {gp.sub_category}"
        if cat_key != current_cat:
            lines.append(f"\n[{cat_key}]")
            current_cat = cat_key
        lines.append(f"  {gp.egp_id} ({gp.level}) {gp.name_zh}")

    return "\n".join(lines)


# ============================================================
# Prompt 构建
# ============================================================

SYSTEM_PROMPT = """你是一位英语语言学专家和语法教学设计师，精通 CEFR 语法体系（A1-C2）。

你的任务是为英语语法点标注「跨类别前置依赖」关系。

「前置依赖」的定义：
学习语法点 B 之前，必须先掌握语法点 A，则 A 是 B 的前置依赖。
这里我们只关注「跨子类」的依赖——即 A 和 B 属于不同的语法子类（SubCategory）。

标注原则：
1. 只标注「必要」的前置依赖，不是「相关」就算依赖
2. 前置依赖的等级必须 ≤ 目标语法点的等级
3. 每个语法点最多标注 5 个跨类前置依赖
4. 如果某个语法点不需要跨类前置依赖，返回空数组
5. 返回严格的 JSON 格式"""


def build_batch_prompt(target_gps, candidate_text, config):
    """
    构建一个批次的标注 prompt。

    Args:
        target_gps: 当前批次要标注的语法点列表
        candidate_text: 候选前置语法点的精简列表
        config: 配置
    """
    max_prereqs = config["annotate"]["max_cross_prereqs"]

    # 构建目标语法点详情
    target_details = []
    for gp in target_gps:
        detail = (
            f"  ID: {gp.egp_id}\n"
            f"  等级: {gp.level}\n"
            f"  分类: {gp.super_category} > {gp.sub_category}\n"
            f"  名称: {gp.name_zh}\n"
            f"  Guideword: {gp.guideword}\n"
            f"  CanDo: {gp.can_do}\n"
            f"  关键词: {', '.join(gp.keywords[:5])}"
        )
        target_details.append(detail)

    targets_text = "\n---\n".join(target_details)
    target_ids = [gp.egp_id for gp in target_gps]

    user_prompt = f"""请为以下 {len(target_gps)} 个语法点标注「跨子类前置依赖」。

## 目标语法点（需要标注的）

{targets_text}

## 候选前置语法点（可选择的依赖来源）

以下是按类别组织的全部语法点列表，请从中选择合适的前置依赖：
{candidate_text}

## 输出要求

请为每个目标语法点，从候选列表中选出 0~{max_prereqs} 个「跨子类」的前置依赖。
注意：前置依赖必须来自与目标语法点「不同的子类」，且等级 ≤ 目标等级。

请严格返回以下 JSON 格式：
{{
  "annotations": [
    {{
      "egp_id": "{target_ids[0]}",
      "cross_prerequisites": ["候选ID_1", "候选ID_2"],
      "reasoning": "简短说明为什么这些是前置依赖"
    }}
  ]
}}"""

    return user_prompt


# ============================================================
# API 调用
# ============================================================

def call_llm(client, config, system_prompt, user_prompt):
    """调用 LLM API"""
    api_cfg = config["api"]
    max_retries = api_cfg.get("max_retries", 3)
    retry_delay = api_cfg.get("retry_delay", 5)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=api_cfg["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=api_cfg.get("temperature", 0.2),
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"    JSON 解析失败 (尝试 {attempt+1}/{max_retries}): {e}")
            # 尝试从响应中提取 JSON
            if content:
                import re
                m = re.search(r'\{[\s\S]*\}', content)
                if m:
                    try:
                        return json.loads(m.group())
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"    API 调用失败 (尝试 {attempt+1}/{max_retries}): {e}")

        if attempt < max_retries - 1:
            print(f"    {retry_delay}s 后重试...")
            time.sleep(retry_delay)

    return None


# ============================================================
# 断点续传
# ============================================================

def load_checkpoint(config):
    """加载断点"""
    checkpoint_file = config["annotate"]["checkpoint_file"]
    filepath = os.path.join(os.path.dirname(__file__), checkpoint_file)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"completed_ids": [], "results": []}


def save_checkpoint(config, checkpoint):
    """保存断点"""
    checkpoint_file = config["annotate"]["checkpoint_file"]
    filepath = os.path.join(os.path.dirname(__file__), checkpoint_file)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def save_results(config, results):
    """保存最终结果"""
    output_file = config["annotate"]["output_file"]
    filepath = os.path.join(os.path.dirname(__file__), output_file)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    output = {
        "metadata": {
            "description": "LLM 标注的跨子类前置依赖关系",
            "total_annotations": len(results),
            "annotated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "annotations": results,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存: {filepath}")
    return filepath


# ============================================================
# 主流程
# ============================================================

def run_annotation(dry_run=False, resume=False):
    """
    运行 LLM 标注流程。

    Args:
        dry_run: 如果为 True，只打印 prompt 不调用 API
        resume: 如果为 True，从断点续传
    """
    print("=" * 60)
    print("  EGP 语法知识图谱 — LLM 跨类依赖标注")
    print("=" * 60)

    config = load_config()
    ann_cfg = config["annotate"]
    batch_size = ann_cfg["batch_size"]
    min_level = ann_cfg["min_level"]

    # 准备数据
    print("\n  加载数据...")
    gp_by_id, gp_by_sub, gp_by_level, all_data = prepare_data()

    level_rank = {lvl: i for i, lvl in enumerate(LEVELS)}
    min_rank = level_rank.get(min_level, 1)

    # 筛选需要标注的语法点（等级 ≥ min_level）
    targets = [gp for gp in all_data if level_rank.get(gp.level, 0) >= min_rank]
    targets.sort(key=lambda g: (level_rank.get(g.level, 99), g.super_category, g.egp_id))

    print(f"  总语法点: {len(all_data)}")
    print(f"  需标注 (≥{min_level}): {len(targets)}")
    print(f"  批次大小: {batch_size}")
    print(f"  预计批次数: {(len(targets) + batch_size - 1) // batch_size}")

    # 断点续传
    checkpoint = {"completed_ids": [], "results": []}
    if resume:
        checkpoint = load_checkpoint(config)
        completed = set(checkpoint["completed_ids"])
        targets = [gp for gp in targets if gp.egp_id not in completed]
        print(f"  已完成: {len(completed)}, 剩余: {len(targets)}")

    if not targets:
        print("\n  所有语法点已标注完成！")
        if checkpoint["results"]:
            save_results(config, checkpoint["results"])
        return

    # 创建客户端
    client = None
    if not dry_run:
        print("\n  连接 API...")
        client = create_client(config)
        print(f"  模型: {config['api']['model']}")
        print(f"  api-key: {config['api']['api_key']}")
        print(f"  Base URL: {config['api']['base_url']}")

    # 分批处理
    total_batches = (len(targets) + batch_size - 1) // batch_size
    all_annotations = list(checkpoint["results"])

    print(f"\n  开始标注 ({total_batches} 个批次)...")
    print("─" * 50)

    for batch_idx in range(0, len(targets), batch_size):
        batch = targets[batch_idx:batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        batch_levels = set(gp.level for gp in batch)

        # 确定候选文本的最大等级
        max_level_rank = max(level_rank.get(gp.level, 0) for gp in batch)
        candidate_text = build_candidate_text(all_data, max_level_rank)

        # 构建 prompt
        user_prompt = build_batch_prompt(batch, candidate_text, config)

        ids_str = ", ".join(gp.egp_id for gp in batch)
        print(f"\n  批次 {batch_num}/{total_batches} | {ids_str}")
        print(f"    等级: {', '.join(sorted(batch_levels))}")
        print(f"    Prompt 长度: ~{len(SYSTEM_PROMPT) + len(user_prompt)} 字符")

        if dry_run:
            print(f"    [DRY RUN] 跳过 API 调用")
            if batch_num <= 2:
                print(f"\n--- Prompt 预览 (批次 {batch_num}) ---")
                print(user_prompt[:500])
                print("... (截断)")
            continue

        # 调用 API
        print(f"    调用 API...")
        result = call_llm(client, config, SYSTEM_PROMPT, user_prompt)

        if result and "annotations" in result:
            annotations = result["annotations"]
            print(f"    返回 {len(annotations)} 条标注")

            for ann in annotations:
                egp_id = ann.get("egp_id", "")
                prereqs = ann.get("cross_prerequisites", [])
                reasoning = ann.get("reasoning", "")

                # 验证：过滤无效的 prerequisite ID
                valid_prereqs = [pid for pid in prereqs if pid in gp_by_id]
                # 验证：确保 prerequisite 来自不同子类
                if egp_id in gp_by_id:
                    target_sub = (gp_by_id[egp_id].super_category, gp_by_id[egp_id].sub_category)
                    valid_prereqs = [
                        pid for pid in valid_prereqs
                        if (gp_by_id[pid].super_category, gp_by_id[pid].sub_category) != target_sub
                    ]

                if valid_prereqs:
                    print(f"    {egp_id}: {len(valid_prereqs)} 个跨类依赖 → {valid_prereqs}")
                else:
                    print(f"    {egp_id}: 无跨类依赖")

                all_annotations.append({
                    "egp_id": egp_id,
                    "cross_prerequisites": valid_prereqs,
                    "reasoning": reasoning,
                })
                checkpoint["completed_ids"].append(egp_id)
        else:
            print(f"    警告: API 返回无效结果，跳过此批次")
            for gp in batch:
                checkpoint["completed_ids"].append(gp.egp_id)

        # 每批次保存断点
        checkpoint["results"] = all_annotations
        save_checkpoint(config, checkpoint)

        # 速率限制：批次间等待
        if batch_idx + batch_size < len(targets):
            time.sleep(1)

    # 保存最终结果
    print("\n" + "─" * 50)
    save_results(config, all_annotations)

    # 统计
    has_prereqs = sum(1 for a in all_annotations if a.get("cross_prerequisites"))
    total_prereqs = sum(len(a.get("cross_prerequisites", [])) for a in all_annotations)
    print(f"\n  标注统计:")
    print(f"    总标注语法点: {len(all_annotations)}")
    print(f"    有跨类依赖的: {has_prereqs}")
    print(f"    跨类依赖总数: {total_prereqs}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    resume = "--resume" in sys.argv

    if dry_run:
        print("  [模式: DRY RUN — 只预览 prompt，不调用 API]\n")

    run_annotation(dry_run=dry_run, resume=resume)
