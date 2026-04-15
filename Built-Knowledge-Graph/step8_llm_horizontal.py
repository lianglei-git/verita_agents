"""
Step 8 (Horizontal): LLM 标注同等级内子类教学顺序

使用 LLM 为每个 CEFR 等级内的 SubCategory 排序，构建横向教学依赖关系。
例如在 A1 内：先教 NOUNS > types，再教 DETERMINERS > articles。

流程：
  1. 提取每个等级包含的所有 SubCategory
  2. 为每个等级构建 Prompt，要求 LLM 对这些 SubCategory 进行教学顺序排序
  3. 调用 API 获取排序结果
  4. 保存为 horizontal_topology.json

运行:
  python step8_llm_horizontal.py              # 执行标注
  python step8_llm_horizontal.py --dry-run    # 仅预览 Prompt
"""

import json
import os
import sys
import time
import yaml
from collections import defaultdict

from step1_ontology import LEVELS
from step2_parse_egp import parse_egp_csv

# 复用 step8 的配置
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "output", "horizontal_topology.json")


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
    return OpenAI(
        api_key=api_cfg["api_key"],
        base_url=api_cfg["base_url"],
    )


def get_subcategories_by_level(data):
    """
    提取每个等级下的 SubCategory 列表。
    返回: {level: [ (super_cat, sub_cat, count, example_topic), ... ]}
    """
    level_subs = defaultdict(lambda: defaultdict(list))
    
    for gp in data:
        key = (gp.super_category, gp.sub_category)
        level_subs[gp.level][key].append(gp)
        
    result = {}
    for lvl in LEVELS:
        subs = []
        for (sc, sub), gps in level_subs[lvl].items():
            # 选一个代表性的 name_zh 作为 topic 示例
            example = gps[0].name_zh if gps else ""
            subs.append({
                "super": sc,
                "sub": sub,
                "count": len(gps),
                "example": example
            })
        # 按类别名排序保证稳定
        subs.sort(key=lambda x: (x["super"], x["sub"]))
        result[lvl] = subs
        
    return result


SYSTEM_PROMPT = """你是一位资深的英语教研员和课程设计专家，精通 CEFR 标准。
你的任务是为特定 CEFR 等级内的语法板块（SubCategory）设计合理的「教学先后顺序」。

目标：
构建一个符合语言习得规律的教学大纲。例如，通常先教名词，再教代词；先教一般现在时，再教现在进行时。

输出要求：
1. 将给定的语法板块分为若干个「教学阶段」（Stages）。
2. 阶段 1 是最基础的，阶段 2 依赖阶段 1，以此类推。
3. 同一阶段内的板块可以平行教学，无强依赖。
4. 返回严格的 JSON 格式。"""


def build_prompt(level, subs):
    """构建单等级排序 Prompt"""
    subs_text = []
    for i, s in enumerate(subs):
        subs_text.append(
            f"ID: {i+1} | 类别: {s['super']} > {s['sub']} | 包含 {s['count']} 个知识点 | 示例: {s['example']}"
        )
    
    subs_block = "\n".join(subs_text)
    
    user_prompt = f"""请为 **{level}** 等级的英语初学者安排以下 {len(subs)} 个语法板块的教学顺序。

## 待排序板块
{subs_block}

## 任务
请将这些板块分配到 3-6 个递进的教学阶段（Stage）中。
- Stage 1: 最核心、最基础的板块（如名词、动词基础、简单句）
- Stage 2: 需要 Stage 1 作为基础的板块
- ...
- Stage N: 该等级中最复杂、综合性最强的板块

## 输出格式 (JSON)
{{
  "level": "{level}",
  "stages": [
    {{
      "stage": 1,
      "description": "阶段描述（如：基础词法与简单句）",
      "items": [ID列表，如 1, 5, 8]
    }},
    ...
  ]
}}
"""
    return user_prompt


def call_llm(client, config, user_prompt):
    api_cfg = config["api"]
    try:
        response = client.chat.completions.create(
            model=api_cfg["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1, # 极低温度保证逻辑严密
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"    API 调用失败: {e}")
        return None


def run_horizontal_sort(dry_run=False):
    print("=" * 60)
    print("  EGP 图谱 — Step 8 (Horizontal): 同级子类排序")
    print("=" * 60)
    
    config = load_config()
    client = None if dry_run else create_client(config)
    
    print("\n  加载并分析数据...")
    data = parse_egp_csv()
    level_subs = get_subcategories_by_level(data)
    
    results = {}
    
    for lvl in LEVELS:
        subs = level_subs[lvl]
        if not subs:
            continue
            
        print(f"\n  处理等级: {lvl} (共 {len(subs)} 个子类)")
        
        prompt = build_prompt(lvl, subs)
        
        if dry_run:
            print("    [DRY RUN] Prompt 预览:")
            print("-" * 40)
            print(prompt[:500] + "\n...")
            print("-" * 40)
            continue
            
        print("    调用 API 获取教学拓扑...")
        resp = call_llm(client, config, prompt)
        
        if resp:
            # 解析 ID 回原来的 key
            stages = []
            for stage in resp.get("stages", []):
                stage_items = []
                for idx in stage.get("items", []):
                    if 1 <= idx <= len(subs):
                        item = subs[idx-1]
                        stage_items.append({
                            "super": item["super"],
                            "sub": item["sub"]
                        })
                stages.append({
                    "stage": stage.get("stage"),
                    "description": stage.get("description", ""),
                    "items": stage_items
                })
            
            results[lvl] = stages
            print(f"    成功: 划分为 {len(stages)} 个教学阶段")
            for s in stages:
                print(f"      Stage {s['stage']} ({len(s['items'])}项): {s['description']}")
        
        time.sleep(2) # 避免限流
        
    if not dry_run:
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n  结果已保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_horizontal_sort(dry_run)
