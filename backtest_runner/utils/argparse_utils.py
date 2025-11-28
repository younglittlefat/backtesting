"""
命令行参数解析工具

提供支持下划线和连字符两种参数格式的 ArgumentParser。
"""

import argparse
import sys
from typing import List, Optional


class UnderscoreHyphenArgumentParser(argparse.ArgumentParser):
    """
    自定义 ArgumentParser，支持下划线和连字符两种参数格式。

    例如: --enable-hysteresis 和 --enable_hysteresis 都被接受，
    内部统一转换为连字符格式处理。

    示例:
        parser = UnderscoreHyphenArgumentParser(description='示例程序')
        parser.add_argument('--enable-feature', action='store_true')
        # 以下两种调用方式都有效:
        # python script.py --enable-feature
        # python script.py --enable_feature
    """

    def parse_args(
        self,
        args: Optional[List[str]] = None,
        namespace: Optional[argparse.Namespace] = None
    ) -> argparse.Namespace:
        """解析参数前，将下划线转换为连字符"""
        if args is None:
            args = sys.argv[1:]

        # 转换下划线为连字符（仅对 -- 开头的长参数）
        normalized_args = []
        for arg in args:
            if arg.startswith('--') and '_' in arg:
                # 分离参数名和可能的 = 后的值
                if '=' in arg:
                    param, value = arg.split('=', 1)
                    normalized_args.append(param.replace('_', '-') + '=' + value)
                else:
                    normalized_args.append(arg.replace('_', '-'))
            else:
                normalized_args.append(arg)

        return super().parse_args(normalized_args, namespace)


def normalize_args(args: Optional[List[str]] = None) -> List[str]:
    """
    将命令行参数中的下划线转换为连字符。

    可用于在调用 argparse 之前预处理参数列表。

    Args:
        args: 命令行参数列表，默认使用 sys.argv[1:]

    Returns:
        标准化后的参数列表
    """
    if args is None:
        args = sys.argv[1:]

    normalized = []
    for arg in args:
        if arg.startswith('--') and '_' in arg:
            if '=' in arg:
                param, value = arg.split('=', 1)
                normalized.append(param.replace('_', '-') + '=' + value)
            else:
                normalized.append(arg.replace('_', '-'))
        else:
            normalized.append(arg)

    return normalized
