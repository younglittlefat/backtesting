#!/usr/bin/env python3
"""
CLI 主入口模块

职责：
- 命令行参数解析
- 参数验证
- 运行时配置加载
- 模式分发（标准模式 vs 轮动模式）
"""

import os
import sys
import warnings
from pathlib import Path

# 禁用进度条输出（在导入backtesting之前设置）
os.environ['BACKTESTING_DISABLE_PROGRESS'] = 'true'

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 过滤掉关于未平仓交易的UserWarning
warnings.filterwarnings('ignore', message='.*Some trades remain open.*')
warnings.filterwarnings('ignore', category=UserWarning, module='backtesting')

from backtest_runner.config import create_argument_parser
from backtest_runner.config.runtime_loader import load_runtime_config


def main() -> int:
    """命令行入口"""
    parser = create_argument_parser()
    args = parser.parse_args()

    # 可选：从配置文件加载参数（与实盘配置统一）
    if getattr(args, 'load_params', None):
        try:
            load_runtime_config(args, args.load_params, args.strategy)
            print(f"从配置加载策略参数: {args.load_params} -> {args.strategy}")
        except Exception as exc:
            print(f"⚠️ 加载配置失败（{args.load_params}）：{exc}")

    # 参数验证
    error = _validate_args(args)
    if error:
        print(error)
        return 1

    # 模式分发
    if hasattr(args, 'enable_rotation') and args.enable_rotation:
        from .rotation_mode import run_rotation_mode
        return run_rotation_mode(args)
    else:
        from .standard_mode import run_standard_mode
        return run_standard_mode(args)


def _validate_args(args) -> str | None:
    """
    验证命令行参数

    Returns:
        错误信息字符串，如果验证通过则返回 None
    """
    # 标的数量限制验证
    if args.instrument_limit is not None and args.instrument_limit <= 0:
        return "\n错误: 标的数量限制必须为正整数。"

    # 轮动模式参数验证
    if hasattr(args, 'enable_rotation') and args.enable_rotation:
        if not args.rotation_schedule:
            return "\n错误: 启用轮动模式时必须指定 --rotation-schedule 参数。"
        if not Path(args.rotation_schedule).exists():
            return f"\n错误: 轮动表文件不存在: {args.rotation_schedule}"

    return None


def print_system_info(args) -> None:
    """打印系统信息"""
    print("=" * 70)
    print("中国市场回测系统")
    print("=" * 70)
    print(f"数据目录:     {args.data_dir}")
    print(f"输出目录:     {args.output_dir}")
    print(f"策略选择:     {args.strategy}")
    print(f"参数优化:     {'是' if args.optimize else '否'}")
    print(f"初始资金:     {args.cash:,.2f}")
    print(f"费用模型:     {args.cost_model}")
    if args.commission is not None:
        print(f"佣金覆盖:     {args.commission:.4%}")
    if args.spread is not None:
        print(f"滑点覆盖:     {args.spread:.4%}")
    if args.category:
        print(f"类别筛选:     {args.category}")
    if args.start_date:
        print(f"开始日期:     {args.start_date}")
    if args.end_date:
        print(f"结束日期:     {args.end_date}")
    if args.instrument_limit is not None:
        print(f"标的数量限制: {args.instrument_limit}")
    if args.verbose:
        print("详细日志:     已启用")
    else:
        print("详细日志:     关闭 (使用 --verbose 查看明细)")
    print("=" * 70)


if __name__ == '__main__':
    sys.exit(main())
