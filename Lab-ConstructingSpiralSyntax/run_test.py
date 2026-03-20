#!/usr/bin/env python3
"""
EGP Spiral Grammar Agent - 测试运行脚本

这个脚本用于方便地运行工作流测试。

使用方法:
    python run_test.py                    # 运行完整测试
    python run_test.py --quick           # 快速测试（跳过Phase 0）
    python run_test.py --phase 1         # 仅测试Phase 1
    python run_test.py --level A2         # 指定等级测试
"""

import subprocess
import sys
from pathlib import Path


def run_test(level="A1", phases=None, quick=False):
    """运行测试脚本"""
    test_script = Path(__file__).parent / "test_workflow.py"
    
    cmd = [sys.executable, str(test_script), "--level", level]
    
    if phases:
        for phase in phases:
            cmd.extend(["--run-phase", str(phase)])
    
    if quick:
        cmd.append("--skip-phase0")
    
    print(f"执行测试命令: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"测试执行失败: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="运行EGP工作流测试")
    parser.add_argument("--level", choices=["A1", "A2", "B1", "B2", "C1", "C2"], 
                       default="A1", help="测试等级")
    parser.add_argument("--phase", type=int, nargs="+", choices=[0, 1, 2, 3],
                       help="指定测试的阶段")
    parser.add_argument("--quick", action="store_true", 
                       help="快速测试（跳过Phase 0）")
    
    args = parser.parse_args()
    
    print("EGP Spiral Grammar Agent - 测试运行器")
    print("=" * 60)
    
    success = run_test(args.level, args.phase, args.quick)
    
    if success:
        print("\n✅ 测试执行完成！")
        print("\n下一步:")
        print("1. 使用真实API运行: python agent.py --level A1 --dry-run")
        print("2. 实际运行Phase 1: python agent.py --level A1 --run-phase 1")
        print("3. 运行完整流程: python agent.py --level A1")
    else:
        print("\n❌ 测试执行失败，请检查错误信息")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())