#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实盘交易信号生成器

每天收盘后运行，分析股票池中的所有标的，生成买入/卖出信号。
适用于双均线策略等技术指标策略。

此文件为向后兼容入口，实际实现已重构到 signal_generator 包中。

作者: Claude Code
日期: 2025-11-07
"""

from signal_generator.cli import main

if __name__ == '__main__':
    main()
