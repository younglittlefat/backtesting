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
import numpy as np


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

    @staticmethod
    def _convert_to_json_serializable(obj):
        """
        递归转换对象为 JSON 可序列化格式

        Args:
            obj: 需要转换的对象

        Returns:
            JSON 可序列化的对象
        """
        if isinstance(obj, dict):
            return {k: StrategyParamsManager._convert_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [StrategyParamsManager._convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif hasattr(obj, '__dict__'):
            return StrategyParamsManager._convert_to_json_serializable(obj.__dict__)
        else:
            return obj

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
        # 转换为 JSON 可序列化格式
        serializable_config = self._convert_to_json_serializable(config)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_config, f, ensure_ascii=False, indent=2)

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
                                notes: str = None,
                                runtime_config: Dict[str, Any] = None):
        """
        保存优化结果（支持运行时配置）

        Args:
            strategy_name: 策略名称
            optimized_params: 优化后的参数
            performance_stats: 性能统计
            optimization_period: 优化数据期间
            stock_pool: 股票池文件
            notes: 备注信息
            runtime_config: 运行时配置（过滤器、止损保护等）
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

        # 保存运行时配置（如果提供）
        if runtime_config:
            config[strategy_name]["runtime_config"] = runtime_config

        self.save_config(config)
        print(f"✓ 已保存策略 {strategy_name} 的优化参数到 {self.config_file}")

    def get_runtime_config(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        获取策略运行时配置

        Args:
            strategy_name: 策略名称

        Returns:
            运行时配置字典，如果不存在则返回 None
        """
        try:
            strategy_info = self.get_strategy_info(strategy_name)
            return strategy_info.get('runtime_config', None)
        except ValueError:
            return None

    def validate_runtime_config(self, config: Dict[str, Any], schema: Dict[str, Any]) -> None:
        """
        验证运行时配置的完整性和参数范围

        Args:
            config: 运行时配置
            schema: 配置结构定义

        Raises:
            ValueError: 配置验证失败
        """
        errors = []

        for section, params in schema.items():
            if section not in config:
                errors.append(f"缺少配置节: {section}")
                continue

            for param_name, param_spec in params.items():
                if param_name not in config[section]:
                    errors.append(
                        f"缺少参数: {section}.{param_name} "
                        f"(默认值: {param_spec.get('default')})"
                    )
                    continue

                value = config[section][param_name]
                param_type = param_spec.get('type')
                param_range = param_spec.get('range')

                # 类型检查
                if param_type == 'int' and not isinstance(value, int):
                    errors.append(f"{section}.{param_name} 应该是整数，实际: {type(value).__name__}")
                elif param_type == 'float' and not isinstance(value, (int, float)):
                    errors.append(f"{section}.{param_name} 应该是浮点数，实际: {type(value).__name__}")
                elif param_type == 'bool' and not isinstance(value, bool):
                    errors.append(f"{section}.{param_name} 应该是布尔值，实际: {type(value).__name__}")

                # 范围检查
                if param_range and isinstance(value, (int, float)):
                    if value < param_range[0] or value > param_range[1]:
                        errors.append(
                            f"{section}.{param_name} 超出范围 {param_range}，实际: {value}"
                        )

        if errors:
            raise ValueError(
                "运行时配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors)
            )

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