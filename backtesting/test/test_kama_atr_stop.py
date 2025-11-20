import numpy as np
import pandas as pd

from backtesting import Backtest
from strategies.kama_cross import KamaCrossStrategy
from strategies.macd_cross import MacdCross
from strategies.sma_cross_enhanced import SmaCrossEnhanced


def _build_trend_dataset() -> pd.DataFrame:
    """
    构造一个先下跌、再上行、随后缓慢回落的价序列，确保：
    1. 出现一次KAMA金叉建仓；
    2. 下跌阶段足够缓慢，使得单纯KAMA死叉发生较晚。
    这样能够检验ATR止损是否能在回撤阶段更早触发平仓。
    """
    segment1 = np.linspace(120, 90, 20)   # 下跌，压低价格到KAMA下方
    segment2 = np.linspace(90, 130, 20)   # 上涨，触发金叉建仓
    segment3 = np.linspace(130, 150, 10)  # 强势上行，抬升动态止损
    segment4 = np.linspace(150, 110, 30)  # 缓慢回落，制造ATR触发窗口
    prices = np.concatenate([segment1, segment2, segment3, segment4])
    index = pd.date_range('2024-01-01', periods=len(prices), freq='D')
    return pd.DataFrame({
        'Open': prices,
        'High': prices + 1,
        'Low': prices - 1,
        'Close': prices,
        'Volume': 1_000,
    }, index=index)


def _build_cross_dataset() -> pd.DataFrame:
    """
    构造一个“下跌→快速上升→温和回落”的序列：
    - 先压低短周期均线；
    - 再快速上行触发金叉；
    - 随后缓慢回撤但不足以触发死叉，由ATR止损提前退出。
    """
    segment1 = np.linspace(80, 70, 15)
    segment2 = np.linspace(70, 110, 20)
    segment3 = np.linspace(110, 95, 10)
    prices = np.concatenate([segment1, segment2, segment3])
    index = pd.date_range('2024-02-01', periods=len(prices), freq='D')
    return pd.DataFrame({
        'Open': prices,
        'High': prices + 0.8,
        'Low': prices - 0.8,
        'Close': prices,
        'Volume': 2_000,
    }, index=index)


def _first_long_exit_bar(stats) -> int:
    longs = stats._trades[stats._trades.Size > 0]
    assert not longs.empty, "期望至少有一次多头交易用于ATR验收"
    return int(longs.ExitBar.iloc[0])


def test_kama_atr_stop_closes_position_earlier():
    """开启ATR止损后，应当早于纯KAMA死叉平仓。"""
    data = _build_trend_dataset()

    base_stats = Backtest(data, KamaCrossStrategy, cash=10_000, commission=0.0).run(
        kama_period=5,
        enable_loss_protection=False,
    )
    atr_stats = Backtest(data, KamaCrossStrategy, cash=10_000, commission=0.0).run(
        kama_period=5,
        enable_loss_protection=False,
        enable_atr_stop=True,
        atr_period=3,
        atr_multiplier=0.5,
    )

    assert len(base_stats._trades) == 1
    assert len(atr_stats._trades) == 1

    exit_bar_base = base_stats._trades.ExitBar.iloc[0]
    exit_bar_atr = atr_stats._trades.ExitBar.iloc[0]

    # ATR应提前触发平仓
    assert exit_bar_atr < exit_bar_base
    assert getattr(atr_stats._strategy, 'atr_stop_hits', 0) >= 1


def test_sma_atr_stop_exits_long_trade_earlier():
    """SMA策略开启ATR止损后，应早于死叉或回测结束退出。"""
    data = _build_cross_dataset()

    base_stats = Backtest(data, SmaCrossEnhanced, cash=10_000, commission=0.0, finalize_trades=True).run(
        n1=5,
        n2=20,
        enable_loss_protection=False,
    )
    atr_stats = Backtest(data, SmaCrossEnhanced, cash=10_000, commission=0.0, finalize_trades=True).run(
        n1=5,
        n2=20,
        enable_loss_protection=False,
        enable_atr_stop=True,
        atr_period=3,
        atr_multiplier=0.6,
    )

    assert _first_long_exit_bar(atr_stats) < _first_long_exit_bar(base_stats)
    assert getattr(atr_stats._strategy, 'atr_stop_hits', 0) >= 1


def test_macd_atr_stop_shortens_long_trade_duration():
    """MACD策略开启ATR止损后，应在回撤中提前退出多头。"""
    data = _build_cross_dataset()

    base_stats = Backtest(data, MacdCross, cash=10_000, commission=0.0, finalize_trades=True).run(
        fast_period=8,
        slow_period=30,
        signal_period=6,
        enable_loss_protection=False,
        enable_trailing_stop=False,
        confirm_bars=1,
        enable_confirm_filter=False,
    )
    atr_stats = Backtest(data, MacdCross, cash=10_000, commission=0.0, finalize_trades=True).run(
        fast_period=8,
        slow_period=30,
        signal_period=6,
        enable_loss_protection=False,
        enable_trailing_stop=False,
        confirm_bars=1,
        enable_confirm_filter=False,
        enable_atr_stop=True,
        atr_period=3,
        atr_multiplier=0.5,
    )

    assert _first_long_exit_bar(atr_stats) < _first_long_exit_bar(base_stats)
    assert getattr(atr_stats._strategy, 'atr_stop_hits', 0) >= 1
