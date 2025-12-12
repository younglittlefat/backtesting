"""
Example usage of the risk management module.

This script demonstrates:
1. ATR calculation and visualization
2. Chandelier Exit stop loss
3. Time-based stop loss
4. Circuit breaker checks
5. Portfolio risk management
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from risk import (
    calculate_atr,
    calculate_stop_line,
    check_stop_loss,
    check_time_stop,
    check_circuit_breaker,
    check_liquidity,
    RiskManager
)


def create_sample_data(start_date='2024-01-01', periods=100, trend='up'):
    """Create sample OHLCV data for demonstration."""
    dates = pd.date_range(start_date, periods=periods, freq='D')
    np.random.seed(42)

    if trend == 'up':
        # Uptrending data
        close = 10.0 + np.arange(periods) * 0.05 + np.random.randn(periods) * 0.2
    elif trend == 'down':
        # Downtrending data
        close = 15.0 - np.arange(periods) * 0.03 + np.random.randn(periods) * 0.2
    else:
        # Sideways data
        close = 10.0 + np.random.randn(periods) * 0.3

    high = close + np.abs(np.random.randn(periods) * 0.2)
    low = close - np.abs(np.random.randn(periods) * 0.2)
    open_price = close + np.random.randn(periods) * 0.1
    volume = np.random.randint(1000000, 5000000, periods)
    amount = close * volume

    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'amount': amount
    }, index=dates)

    return df


def example_1_atr_calculation():
    """Example 1: Calculate and display ATR."""
    print("=" * 60)
    print("Example 1: ATR Calculation")
    print("=" * 60)

    df = create_sample_data(periods=50)

    # Calculate ATR with SMA
    atr_sma = calculate_atr(df, period=14, method='sma')

    # Calculate ATR with EMA
    atr_ema = calculate_atr(df, period=14, method='ema')

    print(f"\nRecent ATR values (last 5 days):")
    print(f"Date          Close    ATR(SMA)  ATR(EMA)")
    print("-" * 50)
    for i in range(-5, 0):
        date = df.index[i]
        close = df.iloc[i]['close']
        atr_s = atr_sma.iloc[i]
        atr_e = atr_ema.iloc[i]
        print(f"{date.date()}  {close:7.2f}  {atr_s:7.3f}   {atr_e:7.3f}")

    print(f"\nATR Summary:")
    print(f"  Average ATR: {atr_sma.mean():.3f}")
    print(f"  Current ATR: {atr_sma.iloc[-1]:.3f}")
    print(f"  ATR as % of price: {(atr_sma.iloc[-1] / df.iloc[-1]['close'] * 100):.2f}%")


def example_2_chandelier_exit():
    """Example 2: Chandelier Exit stop loss."""
    print("\n" + "=" * 60)
    print("Example 2: Chandelier Exit Stop Loss")
    print("=" * 60)

    # Create uptrending data then drop
    df = create_sample_data(periods=50, trend='up')

    entry_date = df.index[10]
    entry_price = df.loc[entry_date, 'close']

    # Calculate stop line
    stop_data = calculate_stop_line(
        df,
        entry_date=entry_date,
        entry_price=entry_price,
        atr_multiplier=3.0
    )

    print(f"\nPosition Entry:")
    print(f"  Date: {entry_date.date()}")
    print(f"  Price: {entry_price:.2f}")

    print(f"\nStop Loss Evolution (last 5 days):")
    print(f"Date          Close    Highest  StopLine  Margin")
    print("-" * 60)
    for i in range(-5, 0):
        date = stop_data.index[i]
        close = stop_data.iloc[i]['close']
        highest = stop_data.iloc[i]['highest_since_entry']
        stop_line = stop_data.iloc[i]['stop_line']
        margin = ((close - stop_line) / close * 100)
        print(f"{date.date()}  {close:7.2f}  {highest:7.2f}  {stop_line:7.2f}  {margin:6.2f}%")

    # Check if stop triggered
    stop_check = check_stop_loss(df, entry_date, entry_price)

    print(f"\nStop Loss Status:")
    print(f"  Triggered: {stop_check['triggered']}")
    print(f"  Days Held: {stop_check['days_held']}")
    print(f"  Current P&L: {stop_check['final_pnl_pct']:.2f}%")


def example_3_time_stop():
    """Example 3: Time-based stop loss."""
    print("\n" + "=" * 60)
    print("Example 3: Time-Based Stop Loss")
    print("=" * 60)

    # Create sideways (stagnant) data
    df = create_sample_data(periods=50, trend='sideways')

    entry_date = df.index[0]
    entry_price = df.loc[entry_date, 'close']

    # Check time stop after 30 days
    result = check_time_stop(
        df,
        entry_date=entry_date,
        entry_price=entry_price,
        max_hold_days=20,
        min_profit_atr=1.0
    )

    print(f"\nPosition Entry:")
    print(f"  Date: {entry_date.date()}")
    print(f"  Price: {entry_price:.2f}")

    print(f"\nTime Stop Check (after {result['days_held']} days):")
    print(f"  Triggered: {result['triggered']}")
    print(f"  Profit: {result['profit_pct']:.2f}%")
    print(f"  Profit in ATR: {result['profit_atr']:.2f}x")
    print(f"  Reason: {result['reason']}")

    if result['triggered']:
        print(f"\n  → Position should be closed to free up capital")
    else:
        print(f"\n  → Position can continue (profitable enough)")


def example_4_circuit_breaker():
    """Example 4: Circuit breaker."""
    print("\n" + "=" * 60)
    print("Example 4: Circuit Breaker")
    print("=" * 60)

    # Create market crash scenario
    dates = pd.date_range('2024-01-01', periods=20, freq='D')
    market_prices = [3000.0 + i * 10 for i in range(15)]  # Uptrend
    market_prices.extend([3150 - i * 50 for i in range(5)])  # Crash

    market_df = pd.DataFrame({'close': market_prices}, index=dates)

    # Create account equity with drawdown
    equity = [100000 + i * 500 for i in range(15)]
    equity.extend([107000 - i * 800 for i in range(5)])
    equity_series = pd.Series(equity, index=dates)

    # Check circuit breaker
    result = check_circuit_breaker(
        market_df=market_df,
        account_equity=equity_series,
        as_of_date=dates[-1],
        market_drop_threshold=-0.05,
        account_drawdown_threshold=-0.03
    )

    print(f"\nMarket Status:")
    print(f"  Current Index: {market_df.iloc[-1]['close']:.0f}")
    print(f"  Change: {result['market_change']:.2%}" if result['market_change'] else "  Change: N/A")

    print(f"\nAccount Status:")
    print(f"  Current Equity: ${equity_series.iloc[-1]:,.0f}")
    print(f"  Peak Equity: ${equity_series.max():,.0f}")
    print(f"  Drawdown: {result['account_drawdown']:.2%}" if result['account_drawdown'] else "  Drawdown: N/A")

    print(f"\nCircuit Breaker:")
    print(f"  Status: {'TRIGGERED' if result['triggered'] else 'OK'}")
    print(f"  Reason: {result['reason']}")

    if result['recommendations']:
        print(f"\nRecommendations:")
        for rec in result['recommendations']:
            print(f"  - {rec}")


def example_5_liquidity_check():
    """Example 5: Liquidity check."""
    print("\n" + "=" * 60)
    print("Example 5: Liquidity Check")
    print("=" * 60)

    # Create high liquidity data
    df_liquid = create_sample_data(periods=30)
    df_liquid['amount'] = 100_000_000  # 100M daily

    # Create low liquidity data
    df_illiquid = create_sample_data(periods=30)
    df_illiquid['amount'] = 20_000_000  # Only 20M daily

    print("\nETF A (High Liquidity):")
    result_a = check_liquidity(df_liquid, min_amount=50_000_000)
    print(f"  Avg Trading Amount: ${result_a['avg_amount']:,.0f}")
    print(f"  Sufficient: {result_a['sufficient']}")

    print("\nETF B (Low Liquidity):")
    result_b = check_liquidity(df_illiquid, min_amount=50_000_000)
    print(f"  Avg Trading Amount: ${result_b['avg_amount']:,.0f}")
    print(f"  Sufficient: {result_b['sufficient']}")
    print(f"  Reason: {result_b['reason']}")


def example_6_risk_manager():
    """Example 6: Comprehensive RiskManager."""
    print("\n" + "=" * 60)
    print("Example 6: Comprehensive RiskManager")
    print("=" * 60)

    # Initialize RiskManager
    config = {
        'atr_multiplier': 3.0,
        'atr_period': 14,
        'time_stop_days': 20,
        'time_stop_min_profit_atr': 1.0,
        'market_drop_threshold': -0.05,
        'account_drawdown_threshold': -0.03,
        'min_liquidity_amount': 50_000_000
    }

    rm = RiskManager(config)

    # Create sample portfolio data
    data_dict = {
        '159915.SZ': create_sample_data(periods=50, trend='up'),
        '510300.SH': create_sample_data(periods=50, trend='down'),
        '512100.SH': create_sample_data(periods=50, trend='sideways')
    }

    positions = {
        '159915.SZ': {
            'entry_date': data_dict['159915.SZ'].index[10],
            'entry_price': data_dict['159915.SZ'].iloc[10]['close']
        },
        '510300.SH': {
            'entry_date': data_dict['510300.SH'].index[10],
            'entry_price': data_dict['510300.SH'].iloc[10]['close']
        },
        '512100.SH': {
            'entry_date': data_dict['512100.SH'].index[0],
            'entry_price': data_dict['512100.SH'].iloc[0]['close']
        }
    }

    # Create market and equity data
    dates = data_dict['159915.SZ'].index
    market_df = pd.DataFrame({'close': 3000.0 + np.arange(len(dates)) * 2}, index=dates)
    equity = pd.Series(100000 + np.arange(len(dates)) * 100, index=dates)

    # Check portfolio risk
    result = rm.check_portfolio_risk(
        data_dict=data_dict,
        positions=positions,
        market_df=market_df,
        account_equity=equity
    )

    print("\nPortfolio Risk Summary:")
    print(f"  Total Positions: {result['summary']['total_positions']}")
    print(f"  ATR Stops Triggered: {result['summary']['atr_stops_triggered']}")
    print(f"  Time Stops Triggered: {result['summary']['time_stops_triggered']}")
    print(f"  Circuit Breaker: {result['summary']['circuit_breaker_active']}")

    print("\nPosition Details:")
    for symbol, risk in result['position_risks'].items():
        print(f"\n  {symbol}:")
        print(f"    Actions: {', '.join(risk['actions'])}")
        print(f"    Can Sell Today: {risk['can_sell_today']}")

        if risk['atr_stop']['triggered']:
            print(f"    ATR Stop: TRIGGERED on {risk['atr_stop']['trigger_date']}")
        if risk['time_stop']['triggered']:
            print(f"    Time Stop: TRIGGERED after {risk['time_stop']['days_held']} days")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("RISK MANAGEMENT MODULE - EXAMPLES")
    print("=" * 60)

    try:
        example_1_atr_calculation()
        example_2_chandelier_exit()
        example_3_time_stop()
        example_4_circuit_breaker()
        example_5_liquidity_check()
        example_6_risk_manager()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
