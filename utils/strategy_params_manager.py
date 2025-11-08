#!/usr/bin/env python3
"""
参数管理工具模块

用于回测和信号生成系统的参数配置文件管理
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class StrategyParamsManager:
    """策略参数管理器"""

    def __init__(self, config_file: str = None):
        """
        初始化参数管理器

        Args:
            config_file: 配置文件路径，默认使用 config/strategy_params.json
        """
        if config_file is None:
            project_root = Path(__file__).parent
            config_file = project_root / "config" / "strategy_params.json"

        self.config_file = Path(config_file)
        self.ensure_config_file()

    def ensure_config_file(self):
        """确保配置文件存在，如果不存在则创建默认配置"""
        if not self.config_file.exists():
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            default_config = {
                "sma_cross": {
                    "optimized": False,
                    "optimization_date": None,
                    "optimization_period": None,
                    "stock_pool": None,
                    "params": {
                        "n1": 10,
                        "n2": 20
                    },
                    "performance": {
                        "sharpe_ratio": None,
                        "annual_return": None,
                        "max_drawdown": None,
                        "return_pct": None
                    },
                    "notes": "默认参数配置"
                }
            }
            self.save_config(default_config)

    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"警告: 加载配置文件失败 ({e})，使用默认配置")
            self.ensure_config_file()
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)

    def save_config(self, config: Dict[str, Any]):
        """保存配置文件"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def get_strategy_params(self, strategy_name: str) -> Dict[str, Any]:
        """
        获取策略参数

        Args:
            strategy_name: 策略名称

        Returns:
            策略参数字典
        """
        config = self.load_config()

        if strategy_name not in config:
            raise ValueError(f"未找到策略配置: {strategy_name}")

        return config[strategy_name]['params']

    def get_strategy_info(self, strategy_name: str) -> Dict[str, Any]:
        """
        获取策略完整信息

        Args:
            strategy_name: 策略名称

        Returns:
            策略完整配置信息
        """
        config = self.load_config()

        if strategy_name not in config:
            raise ValueError(f"未找到策略配置: {strategy_name}")

        return config[strategy_name]

    def save_optimization_results(self,
                                strategy_name: str,
                                optimized_params: Dict[str, Any],
                                performance_stats: Dict[str, float],
                                optimization_period: str = None,
                                stock_pool: str = None,
                                notes: str = None):
        """
        保存优化结果

        Args:
            strategy_name: 策略名称
            optimized_params: 优化后的参数
            performance_stats: 性能统计
            optimization_period: 优化数据期间
            stock_pool: 股票池文件
            notes: 备注信息
        """
        config = self.load_config()

        # 更新策略配置
        if strategy_name not in config:
            config[strategy_name] = {
                "optimized": False,
                "optimization_date": None,
                "optimization_period": None,
                "stock_pool": None,
                "params": {},
                "performance": {},
                "notes": ""
            }

        # 更新参数
        config[strategy_name].update({
            "optimized": True,
            "optimization_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "optimization_period": optimization_period,
            "stock_pool": stock_pool,
            "params": optimized_params,
            "performance": performance_stats,
            "notes": notes or f"参数优化于 {datetime.now().strftime('%Y-%m-%d')}"
        })

        self.save_config(config)
        print(f"✓ 已保存策略 {strategy_name} 的优化参数到 {self.config_file}")

    def is_strategy_optimized(self, strategy_name: str) -> bool:
        """
        检查策略是否已优化

        Args:
            strategy_name: 策略名称

        Returns:
            是否已优化
        """
        try:
            strategy_info = self.get_strategy_info(strategy_name)
            return strategy_info.get('optimized', False)
        except ValueError:
            return False

    def print_strategy_info(self, strategy_name: str):
        """
        打印策略信息

        Args:
            strategy_name: 策略名称
        """
        try:
            strategy_info = self.get_strategy_info(strategy_name)

            print(f"\n策略信息: {strategy_name}")
            print("=" * 50)
            print(f"是否优化: {'是' if strategy_info['optimized'] else '否'}")

            if strategy_info['optimization_date']:
                print(f"优化时间: {strategy_info['optimization_date']}")

            if strategy_info['optimization_period']:
                print(f"数据期间: {strategy_info['optimization_period']}")

            if strategy_info['stock_pool']:
                print(f"股票池: {strategy_info['stock_pool']}")

            print(f"参数:")
            for key, value in strategy_info['params'].items():
                print(f"  {key}: {value}")

            if any(v is not None for v in strategy_info['performance'].values()):
                print(f"性能指标:")
                for key, value in strategy_info['performance'].items():
                    if value is not None:
                        if key in ['sharpe_ratio']:
                            print(f"  {key}: {value:.2f}")
                        elif key in ['annual_return', 'max_drawdown', 'return_pct']:
                            print(f"  {key}: {value:.2f}%")
                        else:
                            print(f"  {key}: {value}")

            if strategy_info.get('notes'):
                print(f"备注: {strategy_info['notes']}")

            print("=" * 50)

        except ValueError as e:
            print(f"错误: {e}")


def main():
    """命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(description='策略参数管理工具')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--strategy', default='sma_cross', help='策略名称')
    parser.add_argument('--show', action='store_true', help='显示策略信息')
    parser.add_argument('--get-params', action='store_true', help='获取策略参数')

    args = parser.parse_args()

    manager = StrategyParamsManager(args.config)

    if args.show:
        manager.print_strategy_info(args.strategy)
    elif args.get_params:
        try:
            params = manager.get_strategy_params(args.strategy)
            for key, value in params.items():
                print(f"{key}: {value}")
        except ValueError as e:
            print(f"错误: {e}")
    else:
        print("请指定操作: --show 或 --get-params")


if __name__ == '__main__':
    main()