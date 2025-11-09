#!/usr/bin/env python3
"""
中国市场回测执行器 (兼容入口)

使用 backtesting.py 框架对中国 ETF/基金等标的进行批量回测

注意：此文件已重构为轻量级入口，实际逻辑在 backtest_runner 包中。
保留此文件是为了向后兼容，run_backtest.sh 等脚本可继续使用。
"""

if __name__ == '__main__':
    import sys
    from backtest_runner.cli import main
    sys.exit(main())
