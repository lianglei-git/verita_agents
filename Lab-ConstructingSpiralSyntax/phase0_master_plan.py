"""
Phase 0: 学习大纲生成与校验（Master Plan Generation）

根据SKILL.md描述，这是第一阶段，负责生成整体学习大纲并通过多个校验师进行校验，
直到置信度达到85%以上。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
import importlib
from typing import Any

from config import CEFR_LEVELS, get_config
from llm_client import LLMClient

dotenv = importlib.import_module("dotenv") if importlib.util.find_spec("dotenv") else None
if dotenv is not None:
    dotenv.load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("phase0_master_plan")

# 根据SKILL.md定义的响应格式
MASTER_RESPONSE_SCHEMA = {
    "finalResult": "学习顺序大纲",
    "score": "置信度评分",
    "finalSuggestion": "最终建议",
    "timestamp": "2026-03-19 14:30:00"
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 0: 生成学习大纲并进行多轮校验，直到置信度达标。",
    )
    parser.add_argument("--level", choices=list(CEFR_LEVELS), default="A1", help="CEFR level")
    parser.add_argument("--lang", default="en", help="Language code")
    parser.add_argument("--model", default=None, help="Override LLM model")
    parser.add_argument("--threshold", type=float, default=0.85, help="置信度阈值 (default: 0.85)")
    parser.add_argument("--max-iterations", type=int, default=5, help="最大迭代次数 (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run模式，不实际调用API")
    parser.add_argument("--force-rerun", action="store_true", help="强制重新运行，忽略缓存")
    return parser.parse_args()

def load_csv_data(cfg) -> list[dict[str, Any]]:
    """加载CSV数据用于分析"""
    try:
        import pandas as pd
        df = pd.read_csv(cfg.egp_csv_path)
        return df.to_dict('records')
    except Exception as e:
        logger.error("Failed to load CSV data: %s", e)
        sys.exit(1)

def build_master_prompt(cfg, level: str, csv_data: list[dict[str, Any]]) -> str:
    """构建主大纲生成提示词"""
    fixed_prompt = """
你精通英语CEFR的设计原则以及精通语言教学，母语为中文，现在需要为当前等级生成螺旋上升的学习大纲。你的任务是将语法点按照由易到难、循环递进的顺序排列，必须遵循"认知负荷递增"原则，分为若干阶段，总进度0-100分。

重要指导原则：
1. 不要只按语法范畴分类，而要考虑组与组之间的衔接关系
2. 同一语法范畴的条目应该落在相近分数区间，形成模块连贯的学习路径
3. 优先高频、基础、前置依赖少的语法点
4. 确保每个阶段在巩固前序知识的基础上自然引入新内容

每个阶段需要包含：
- 骨架名称：概括该阶段主题
- 进度分数：合理的分数分配，总分为100分
- 学习方针：指导学习重点和方法
- 路径清单：仅知识点名称，按学习顺序排列

请确保学习路径具有明确的进度感，形成小螺旋上升的递进关系。
"""
    
    csv_count = len(csv_data)
    
    prompt = (
        f"{fixed_prompt}\n\n"
        "将 {当前等级} 语法点按照由易到难、循环递进的顺序排列，必须遵循'认知负荷递增'原则，"
        "分为若干阶段，总进度0-100分。不要只按语法范畴分类，而要考虑组与组之间的衔接关系。"
        "基于我提供的EGP CSV数据(包含{数量}个{等级}语法点)重新生成学习路径。\n\n"
        f"当前等级：{level}\n"
        f"语法点数量：{csv_count}\n\n"
        "输出内容要求：每个阶段需包含骨架名称（概括该阶段主题）、进度分数、学习方针（指导学习重点和方法）、"
        "路径清单（仅知识点名称，按学习顺序排列）。"
    )
    
    return prompt

def build_validator1_prompt(master_result: str) -> str:
    """构建校验师1的提示词"""
    return (
        "你是一名深耕 CEFR 标准与 English Grammar Profile (EGP) 的资深课程架构师，负责检验学习顺序合理性。"
        "参考标准如下：\n"
        "1. 使用频率（高频优先）：在真实语料中（如电影、日常对话、学术文章），出现频率最高的结构和词汇应该先学。\n"
        "2. 认知难度（由简入繁）：具体、规则、无太多例外的情况先学；抽象、不规则、需要强语境理解的后学。\n"
        "3. 交际需求（急用先行）：学习者最急需表达的功能先学。\n\n"
        "请校验以下学习顺序是否符合学习顺序要求，置信度由0-100%表示，如果低于85%，请告警并提出建议。\n\n"
        f"{master_result}"
    )

def build_validator2_prompt(master_result: str) -> str:
    """构建校验师2的提示词"""
    return (
        "你是一名专门研究第二语言习得（SLA）顺序的资深研究员，擅长应用 Pienemann 的可加工性理论（Processability Theory）"
        "和认知负荷理论对下方提供的学习顺序进行深度审计，寻找逻辑漏洞。\n\n"
        "审计维度：\n"
        "1. 结构复杂度：是否存在后置阶段的语法结构在处理难度上反而低于前置阶段的情况？\n"
        "2. 认知跃迁：某两个相邻阶段之间是否存在'难度断层'？（即：缺乏足够的过渡知识）。\n"
        "3. 习得规律：顺序是否违反了自然的习得路径（如：在掌握简单从句前就引入了复杂的倒装结构）？\n\n"
        "请校验以下学习顺序是否符合学习顺序要求，置信度由0-100%表示，如果低于85%，请告警并提出建议。\n\n"
        f"{master_result}"
    )

def build_final_validator_prompt(master_result: str, validator1_feedback: str, validator2_feedback: str) -> str:
    """构建最终校验师的提示词"""
    return (
        "请根据输入数据：并基于两个校验师的反馈，给出最终的置信度评分。\n\n"
        f"输入数据：\n{master_result}\n\n"
        f"校验师1反馈：\n{validator1_feedback}\n\n"
        f"校验师2反馈：\n{validator2_feedback}\n\n"
        "输出要求：置信度：0-100%，如果低于85%，请告警并提出建议。"
    )

def extract_confidence_from_response(response_text: str) -> float:
    """从响应文本中提取置信度评分"""
    import re
    # 改进的匹配逻辑：更灵活地匹配关键词后面的第一个数字
    # 支持多种格式：置信度、confidence、score等关键词，后面跟着的数字可能有%等符号
    patterns = [
        # 关键词在前，数字在后（支持特殊字符和百分比）
        r'(?:置信度|confidence|score|评分)[：:]\s*[^\d]*(\d+(?:\.\d+)?)[^\d\%]*\%?',
        # 数字在前，关键词在后
        r'(\d+(?:\.\d+)?)[^\d\%]*\%?\s*(?:置信度|confidence|score|评分)',
        # 简单的数字百分比（可能是单独的数字）
        r'\b(\d+(?:\.\d+)?)\s*\%',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            try:
                score_str = match.group(1)
                # 清理可能的非数字字符
                score_str = re.sub(r'[^\d\.]', '', score_str)
                score = float(score_str)
                
                # 如果匹配到的是百分比格式，需要转换为0-1的小数
                if score > 1 and score <= 100:
                    return score / 100
                elif score <= 1:
                    return score
                # 如果大于100，可能是出错了，返回默认值
            except (ValueError, TypeError):
                continue
    
    # 如果上面的模式都没匹配到，尝试更通用的提取方法
    # 查找所有可能的数字，然后检查它们是否在合理的置信度范围内
    numbers = re.findall(r'\b\d+(?:\.\d+)?\b', response_text)
    processed_scores = []
    
    for num_str in numbers:
        try:
            score = float(num_str)
            # 收集所有在合理范围内的数字
            if 0 <= score <= 100:
                processed_scores.append(score)
        except ValueError:
            continue
    
    # 如果找到了多个数字，优先选择在常见的置信度范围内的数字
    for score in processed_scores:
        # 优先选择接近常见置信度（如70-99）的数字
        if 70 <= score <= 99:
            return score / 100 if score > 1 else score
        elif 0.7 <= score <= 0.99:
            return score
    
    # 如果没有找到合适的数字，返回第一个在合理范围内的数字
    for score in processed_scores:
        if score > 1:
            return min(score / 100, 1.0)
        else:
            return score
    
    return 0.0  # 默认返回0

def run_phase0_iteration(llm: LLMClient, cfg, level: str, csv_data: list[dict[str, Any]], iteration: int) -> dict[str, Any]:
    """执行一次Phase 0迭代"""
    logger.info("Phase 0 第 %d 次迭代", iteration)
    
    # 生成主大纲
    master_prompt = build_master_prompt(cfg, level, csv_data)
    master_response = llm.chat(master_prompt, "请严格按照要求的格式输出学习大纲。")
    
    # 校验师1
    validator1_prompt = build_validator1_prompt(master_response)
    validator1_response = llm.chat(validator1_prompt, "请输出置信度评分和建议。")
    validator1_confidence = extract_confidence_from_response(validator1_response)
    
    # 校验师2
    validator2_prompt = build_validator2_prompt(master_response)
    validator2_response = llm.chat(validator2_prompt, "请输出置信度评分和建议。")
    validator2_confidence = extract_confidence_from_response(validator2_response)
    
    # 最终校验
    final_prompt = build_final_validator_prompt(master_response, validator1_response, validator2_response)
    final_response = llm.chat(final_prompt, "请给出最终的置信度评分。")
    final_confidence = extract_confidence_from_response(final_response)
    
    # 如果两个校验师都低于85%，使用最终校验的置信度
    if validator1_confidence < 0.85 and validator2_confidence < 0.85:
        overall_confidence = final_confidence
    else:
        # 取两个校验师中的较高者
        overall_confidence = max(validator1_confidence, validator2_confidence)
    
    return {
        "iteration": iteration,
        "master_result": master_response,
        "validator1_feedback": validator1_response,
        "validator2_feedback": validator2_response,
        "final_feedback": final_response,
        "validator1_confidence": validator1_confidence,
        "validator2_confidence": validator2_confidence,
        "final_confidence": final_confidence,
        "overall_confidence": overall_confidence,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat()
    }

def build_output_document(cfg, level: str, iterations: list[dict[str, Any]], final_confidence: float) -> dict[str, Any]:
    """构建最终的输出文档"""
    now = datetime.now(timezone.utc).astimezone().isoformat()
    
    # 构建changelog
    changelog = []
    for iteration in iterations:
        changelog.append({
            "timestamp": iteration["timestamp"],
            "finalResult": iteration["master_result"],
            "change": f"第{iteration['iteration']}次迭代",
            "validator1": iteration["validator1_feedback"],
            "validator2": iteration["validator2_feedback"],
            "finalSuggestion": iteration["final_feedback"]
        })
    
    return {
        "LearningSyllabus": {
            "finalResult": iterations[-1]["master_result"] if iterations else "",
            "score": final_confidence,
            "finalSuggestion": iterations[-1]["final_feedback"] if iterations else "",
            "timestamp": now,
            "changeLog": changelog
        }
    }

def dry_run_phase0(cfg, level: str, result_path: Path, latest_path: Path) -> dict:
    """模拟Phase 0的学习大纲生成过程"""
    logger.info("Dry run模式 - 模拟Phase 0学习大纲生成")
    
    # 创建模拟的学习大纲
    master_plan = {
        "finalResult": f"模拟 {level} 等级学习大纲",
        "score": 0.92,
        "finalSuggestion": "通过模拟校验，大纲质量良好，置信度92%",
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat()
    }
    
    # 构建输出文档
    output_doc = {
        "LearningSyllabus": {
            **master_plan,
            "changeLog": [
                {
                    "timestamp": master_plan["timestamp"],
                    "finalResult": master_plan["finalResult"],
                    "change": "第1次迭代",
                    "validator1": "模拟校验师1反馈：语法点安排合理",
                    "validator2": "模拟校验师2反馈：螺旋递进顺序良好",
                    "finalSuggestion": master_plan["finalSuggestion"]
                }
            ]
        }
    }
    
    # 保存结果
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(output_doc, f, ensure_ascii=False, indent=2)
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(output_doc, f, ensure_ascii=False, indent=2)
    
    return output_doc


def main() -> None:
    args = parse_args()
    cfg = get_config(level=args.level, lang=args.lang)
    if args.model:
        cfg.llm.model = args.model
    

    # 检查缓存
    cache_dir = Path("output") / args.level / "phase0"
    cache_file = cache_dir / "prompt.json"
    
    if not args.force_rerun and cache_file.exists():
        logger.info(f"使用缓存文件: {cache_file}")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            confidence = cached_data.get("LearningSyllabus", {}).get("score", 0)
            logger.info(f"✓ Phase 0 已完成 (使用缓存)，置信度: {confidence:.1%}")
            return
        except Exception as e:
            logger.warning(f"缓存文件读取失败: {e}")

    # Dry run模式处理
    if args.dry_run:
        logger.info("Phase 0 Dry run模式启动")
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建结果路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_path = cache_dir / f"prompt_{timestamp}.json"
        latest_path = cache_dir / "prompt.json"
        
        output_doc = dry_run_phase0(cfg, args.level, result_path, latest_path)
        
        confidence = output_doc.get("LearningSyllabus", {}).get("score", 0)
        logger.info("✓ Phase 0 Dry run完成，置信度: %.1f%%", confidence * 100)
        logger.info("生成的文件:")
        logger.info("  - %s", result_path)
        logger.info("  - %s", latest_path)
        return

    if not cfg.llm.api_key:
        logger.error("OPENAI_API_KEY is not set")
        sys.exit(1)

    # 加载CSV数据
    csv_data = load_csv_data(cfg)
    logger.info("Loaded %s CSV records for level %s", len(csv_data), args.level)

    llm = LLMClient(cfg.llm)
    iterations = []
    
    # 运行迭代直到置信度达标或达到最大迭代次数
    for i in range(args.max_iterations):
        iteration_result = run_phase0_iteration(llm, cfg, args.level, csv_data, i + 1)
        iterations.append(iteration_result)
        
        confidence = iteration_result["overall_confidence"]
        logger.info("迭代 %d: 置信度 = %.2f%%", i + 1, confidence * 100)
        
        if confidence >= args.threshold:
            logger.info("置信度达标 (%.2f%% >= %.2f%%)，停止迭代", confidence * 100, args.threshold * 100)
            break
        elif i == args.max_iterations - 1:
            logger.warning("达到最大迭代次数，最终置信度 = %.2f%%", confidence * 100)
        else:
            logger.info("置信度未达标，继续迭代")

    # 生成最终输出
    final_confidence = iterations[-1]["overall_confidence"] if iterations else 0.0
    output_doc = build_output_document(cfg, args.level, iterations, final_confidence)
    
    # 确保输出目录存在
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    
    # 写入prompt.json文件
    prompt_path = cfg.output_dir / "prompt.json"
    with open(prompt_path, 'w', encoding='utf-8') as f:
        json.dump(output_doc, f, ensure_ascii=False, indent=2)
    
    logger.info("Phase 0 完成，输出文件: %s", prompt_path)
    logger.info("最终置信度: %.2f%%", final_confidence * 100)

if __name__ == "__main__":
    main()