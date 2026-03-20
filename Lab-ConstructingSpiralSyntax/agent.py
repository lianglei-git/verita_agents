"""
EGP Spiral Grammar Agent - 整合四个阶段的执行流程

Phase 0: 学习大纲生成
Phase 1: 语法评分与全量排序
Phase 2: 同分数组内排序
Phase 3: 学习路径校验

使用方法:
    python agent.py --level A1 --run-phase 0       # 仅运行 Phase 0
    python agent.py --level A1 --run-phase 1       # 仅运行 Phase 1
    python agent.py --level A1 --run-phase 2       # 仅运行 Phase 2
    python agent.py --level A1 --run-phase 3       # 仅运行 Phase 3
    python agent.py --level A1                     # 运行全部四个阶段
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="EGP Spiral Grammar Agent - 整合三个阶段的执行流程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python agent.py --level A1                          # 运行全部四个阶段
    python agent.py --level A1 --run-phase 0           # 仅运行 Phase 0
    python agent.py --level A1 --run-phase 1           # 仅运行 Phase 1
    python agent.py --level A2 --run-phase 2 --llm    # Phase 2 使用 LLM 排序
    python agent.py --level B1 --run-phase 3           # 仅运行 Phase 3 校验
    python agent.py --level A1 --dry-run              # 仅显示命令，不实际运行
    python agent.py --level A1 --force-rerun          # 强制重新运行，忽略缓存
        """,
    )
    parser.add_argument(
        "--level",
        choices=CEFR_LEVELS,
        default="A1",
        help="CEFR 等级 (default: A1)",
    )
    parser.add_argument(
        "--lang",
        default="en",
        help="语言代码 (default: en)",
    )
    parser.add_argument(
        "--run-phase",
        type=int,
        choices=[0, 1, 2, 3],
        help="指定运行哪个阶段 (0/1/2/3)，不指定则运行全部阶段",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="覆盖 LLM 模型名称",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅显示将要执行的命令，不实际运行",
    )
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="强制重新运行，忽略缓存",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="某个阶段失败时继续执行后续阶段",
    )
    parser.add_argument(
        "--phase2-llm",
        action="store_true",
        help="Phase 2 使用 LLM 进行同分数组内排序 (默认使用 EGP ID 排序)",
    )
    parser.add_argument(
        "--phase3-samples",
        type=int,
        default=3,
        help="Phase 3 抽样次数 (default: 3)",
    )
    parser.add_argument(
        "--phase3-sample-size",
        type=int,
        default=20,
        help="Phase 3 每次抽样条数 (default: 20)",
    )
    return parser.parse_args()


def get_script_path(script_name: str) -> Path:
    """获取脚本路径"""
    base_dir = Path(__file__).parent
    return base_dir / script_name


def run_phase0(level: str, lang: str, model: str | None, dry_run: bool = False, force_rerun: bool = False) -> bool:
    """运行 Phase 0: 学习大纲生成"""
    script = get_script_path("phase0_master_plan.py")
    
    # 检查缓存
    cache_dir = Path(__file__).parent / "output" / level
    cache_file = cache_dir / "prompt.json"
    
    if not force_rerun and cache_file.exists():
        print(f"\n{'='*60}")
        print(f"Phase 0: 学习大纲生成 (使用缓存)")
        print(f"Level: {level}, Lang: {lang}")
        print(f"缓存文件: {cache_file}")
        print(f"{'='*60}\n")
        return True
    
    cmd = [sys.executable, str(script), "--level", level, "--lang", lang]
    
    if model:
        cmd.extend(["--model", model])
    
    print(f"\n{'='*60}")
    print(f"Phase 0: 学习大纲生成")
    print(f"Level: {level}, Lang: {lang}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    if dry_run:
        print("[DRY RUN] Phase 0 命令已准备好")
        return True
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Phase 0 执行失败: {e}")
        return False


def run_phase1(level: str, lang: str, model: str | None, dry_run: bool = False, force_rerun: bool = False) -> bool:
    """运行 Phase 1: 语法评分与全量排序"""
    script = get_script_path("phase1_rough_sorting.py")
    
    # 检查缓存
    possible_paths = [
        Path(__file__).parent  / "output"/ level / "phase1" / "full_sort_latest.json",
        Path(__file__).parent  / "output"/ level / "phase1" / "scored_items_latest.json"
    ]
    
    cache_file = None
    for path in possible_paths:
        if path.exists():
            cache_file = path
            break
    
    
    if not force_rerun and cache_file is not None:
        print(f"\n{'='*60}")
        print(f"Phase 1: 语法评分与全量排序 (使用缓存)")
        print(f"Level: {level}, Lang: {lang}")
        print(f"缓存文件: {cache_file}")
        print(f"{'='*60}\n")
        return True
    
    cmd = [sys.executable, str(script), "--level", level, "--lang", lang, "--plugin", "full-sort"]
    
    if model:
        cmd.extend(["--model", model])
    
    print(f"\n{'='*60}")
    print(f"Phase 1: 语法评分与全量排序")
    print(f"Level: {level}, Lang: {lang}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    if dry_run:
        print("[DRY RUN] Phase 1 命令已准备好")
        return True
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Phase 1 执行失败: {e}")
        return False


def run_phase2(
    level: str,
    lang: str,
    model: str | None,
    use_llm: bool = False,
    dry_run: bool = False,
    force_rerun: bool = False,
) -> bool:
    """运行 Phase 2: 同分数组内排序"""
    script = get_script_path("phase2_same_score_order.py")
    
    # 检查缓存
    cache_dir = Path(__file__).parent / "output" / level / "phase2"
    cache_file = cache_dir / "group_ordering.json"
    
    if not force_rerun and cache_file.exists():
        print(f"\n{'='*60}")
        print(f"Phase 2: 同分数组内排序 (使用缓存)")
        print(f"Level: {level}, Lang: {lang}")
        print(f"Use LLM: {use_llm}")
        print(f"缓存文件: {cache_file}")
        print(f"{'='*60}\n")
        return True
    
    cmd = [sys.executable, str(script), "--level", level, "--lang", lang]
    
    if model:
        cmd.extend(["--model", model])
    
    if use_llm:
        cmd.append("--llm")
    
    print(f"\n{'='*60}")
    print(f"Phase 2: 同分数组内排序")
    print(f"Level: {level}, Lang: {lang}")
    print(f"Use LLM: {use_llm}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    if dry_run:
        print("[DRY RUN] Phase 2 命令已准备好")
        return True
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Phase 2 执行失败: {e}")
        return False


def run_phase3(
    level: str,
    lang: str,
    model: str | None,
    samples: int = 3,
    sample_size: int = 20,
    dry_run: bool = False,
    force_rerun: bool = False,
) -> bool:
    """运行 Phase 3: 学习路径校验"""
    script = get_script_path("phase3_path_check.py")
    
    # 检查缓存
    cache_dir = Path(__file__).parent / "output" / level / "phase3"
    cache_file = cache_dir / "path_validation.json"
    
    if not force_rerun and cache_file.exists():
        print(f"\n{'='*60}")
        print(f"Phase 3: 学习路径校验 (使用缓存)")
        print(f"Level: {level}, Lang: {lang}")
        print(f"Samples: {samples} x {sample_size}")
        print(f"缓存文件: {cache_file}")
        print(f"{'='*60}\n")
        return True
    
    cmd = [
        sys.executable,
        str(script),
        "--level", level,
        "--lang", lang,
        "--samples", str(samples),
        "--sample-size", str(sample_size),
    ]

    if force_rerun:
        cmd.append("--force-rerun")
    
    if model:
        cmd.extend(["--model", model])
    
    print(f"\n{'='*60}")
    print(f"Phase 3: 学习路径校验")
    print(f"Level: {level}, Lang: {lang}")
    print(f"Samples: {samples} x {sample_size}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    if dry_run:
        print("[DRY RUN] Phase 3 命令已准备好")
        return True
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Phase 3 执行失败: {e}")
        return False


def main() -> int:
    args = parse_args()
    
    print(f"\n{'#'*60}")
    print(f"# EGP Spiral Grammar Agent")
    print(f"# Run Phase: {args.run_phase or 'All (0, 1, 2, 3)'}")
    
    phases_to_run = [args.run_phase] if args.run_phase else [0, 1, 2, 3]
    
    results = {}
    
    for phase in phases_to_run:
        if phase == 0:
            success = run_phase0(args.level, args.lang, args.model, args.dry_run, args.force_rerun)
            results[0] = success
            if not success and not args.continue_on_error:
                print("\n[STOP] Phase 0 失败，停止执行")
                return 1
                
        elif phase == 1:
            success = run_phase1(args.level, args.lang, args.model, args.dry_run, args.force_rerun)
            results[1] = success
            if not success and not args.continue_on_error:
                print("\n[STOP] Phase 1 失败，停止执行")
                return 1
                
        elif phase == 2:
            success = run_phase2(
                args.level,
                args.lang,
                args.model,
                args.phase2_llm,
                args.dry_run,
                args.force_rerun,
            )
            results[2] = success
            if not success and not args.continue_on_error:
                print("\n[STOP] Phase 2 失败，停止执行")
                return 1
                
        elif phase == 3:
            success = run_phase3(
                args.level,
                args.lang,
                args.model,
                args.phase3_samples,
                args.phase3_sample_size,
                args.dry_run,
                args.force_rerun,
            )
            results[3] = success
            if not success and not args.continue_on_error:
                print("\n[STOP] Phase 3 失败，停止执行")
                return 1
    
    print(f"\n{'='*60}")
    print(f"执行结果汇总:")
    for phase, success in results.items():
        status = "✓ 成功" if success else "✗ 失败"
        print(f"  Phase {phase}: {status}")
    print(f"{'='*60}\n")
    
    if all(results.values()):
        print("[DONE] 所有阶段执行完成！")
        return 0
    else:
        print("[WARN] 部分阶段执行失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
    