#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
报告打印模块

提供交易信号报告、持仓状态、交易计划的打印功能。
"""

from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

# 延迟导入类型，避免循环依赖
# from portfolio_manager import Portfolio, Trade


def print_signal_report(signals_df: pd.DataFrame,
                       allocation: Dict,
                       output_file: Optional[str] = None):
    """
    打印信号报告

    Args:
        signals_df: 信号DataFrame
        allocation: 资金分配字典
        output_file: 输出文件路径（可选）
    """
    lines = []

    # 标题
    lines.append("=" * 80)
    lines.append(f"交易信号报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append("")

    # 统计摘要
    lines.append("📊 信号统计")
    lines.append("-" * 80)
    signal_counts = signals_df['signal'].value_counts()
    for signal, count in signal_counts.items():
        lines.append(f"  {signal}: {count} 只")
    lines.append("")

    # 买入信号详情
    buy_signals = signals_df[signals_df['signal'] == 'BUY']
    if len(buy_signals) > 0:
        lines.append("🔔 买入信号（金叉）")
        lines.append("-" * 80)
        for _, row in buy_signals.iterrows():
            lines.append(f"  {row['ts_code']}")
            lines.append(f"    当前价格: ¥{row['price']:.3f}")
            lines.append(f"    短期均线: {row['sma_short']:.3f}")
            lines.append(f"    长期均线: {row['sma_long']:.3f}")
            lines.append(f"    信号强度: {row['signal_strength']:.2f}%")
            lines.append(f"    说明: {row['message']}")
            lines.append("")

    # 卖出信号详情
    sell_signals = signals_df[signals_df['signal'] == 'SELL']
    if len(sell_signals) > 0:
        lines.append("📉 卖出信号（死叉）")
        lines.append("-" * 80)
        for _, row in sell_signals.iterrows():
            lines.append(f"  {row['ts_code']}")
            lines.append(f"    当前价格: ¥{row['price']:.3f}")
            lines.append(f"    说明: {row['message']}")
            lines.append("")

    # 资金分配建议
    lines.append("💰 资金分配建议")
    lines.append("-" * 80)
    lines.append(f"  总资金: ¥{allocation['total_cash']:,.2f}")

    if len(allocation['positions']) > 0:
        lines.append(f"  分配资金: ¥{allocation['allocated_cash']:,.2f}")
        lines.append(f"  剩余资金: ¥{allocation['remaining_cash']:,.2f}")
        lines.append(f"  建议持仓数: {allocation['n_positions']}")
        lines.append("")
        lines.append("  具体买入建议:")
        lines.append("")

        for i, pos in enumerate(allocation['positions'], 1):
            lines.append(f"  [{i}] {pos['ts_code']}")
            lines.append(f"      买入价格: ¥{pos['price']:.3f}")
            lines.append(f"      买入数量: {pos['shares']} 股")
            lines.append(f"      预计成本: ¥{pos['cost']:,.2f}")
            lines.append(f"      仓位占比: {pos['weight']:.2f}%")
            lines.append(f"      信号强度: {pos['signal_strength']:.2f}%")
            lines.append("")
    else:
        lines.append(f"  {allocation.get('message', '无买入建议')}")
        lines.append("")

    # 持仓状态
    hold_long = signals_df[signals_df['signal'] == 'HOLD_LONG']
    if len(hold_long) > 0:
        lines.append("✅ 持有多头（继续持有）")
        lines.append("-" * 80)
        for _, row in hold_long.iterrows():
            lines.append(f"  {row['ts_code']}: {row['message']}")
        lines.append("")

    # 打印到控制台
    report = "\n".join(lines)
    print(report)

    # 保存到文件
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"报告已保存到: {output_file}")


def print_portfolio_status(portfolio,
                          current_prices: Dict[str, float],
                          max_positions: int):
    """
    打印持仓状态报告

    Args:
        portfolio: Portfolio 对象
        current_prices: 当前价格字典
        max_positions: 最大持仓数
    """
    lines = []

    lines.append("=" * 80)
    lines.append("当前持仓状态")
    lines.append("=" * 80)
    lines.append("")

    # 资金信息
    market_value = portfolio.get_total_market_value(current_prices)
    total_cost = portfolio.get_total_cost()
    total_pnl = portfolio.get_total_pnl(current_prices)
    total_assets = portfolio.cash + market_value
    pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    lines.append("💰 资金信息")
    lines.append("-" * 80)
    lines.append(f"  可用现金: ¥{portfolio.cash:,.2f}")
    lines.append(f"  持仓市值: ¥{market_value:,.2f}")
    lines.append(f"  总资产:   ¥{total_assets:,.2f}")
    pnl_sign = '+' if total_pnl >= 0 else ''
    lines.append(f"  持仓盈亏: {pnl_sign}¥{total_pnl:,.2f} ({pnl_sign}{pnl_pct:.2f}%)")
    lines.append("")

    # 持仓明细
    lines.append(f"📊 持仓明细 ({len(portfolio.positions)}/{max_positions})")
    lines.append("-" * 80)

    if portfolio.positions:
        for pos in portfolio.positions:
            current_price = current_prices.get(pos.ts_code, pos.entry_price)
            current_value = pos.shares * current_price
            pnl = current_value - pos.cost
            pnl_pct_pos = (pnl / pos.cost * 100) if pos.cost > 0 else 0
            pnl_sign = '+' if pnl >= 0 else ''

            lines.append(f"  {pos.ts_code}")
            lines.append(f"    持仓数量: {pos.shares} 股")
            lines.append(f"    买入价格: ¥{pos.entry_price:.3f} ({pos.entry_date})")
            lines.append(f"    当前价格: ¥{current_price:.3f}")
            lines.append(f"    持仓成本: ¥{pos.cost:,.2f}")
            lines.append(f"    当前市值: ¥{current_value:,.2f}")
            lines.append(f"    盈亏:     {pnl_sign}¥{pnl:,.2f} ({pnl_sign}{pnl_pct_pos:.2f}%)")
            lines.append("")
    else:
        lines.append("  (无持仓)")
        lines.append("")

    lines.append(f"最后更新: {portfolio.last_update}")
    lines.append("=" * 80)

    print("\n".join(lines))


def print_trade_plan(sell_trades: List,
                    buy_trades: List,
                    portfolio):
    """
    打印交易计划

    Args:
        sell_trades: 卖出交易列表 (Trade对象)
        buy_trades: 买入交易列表 (Trade对象)
        portfolio: 当前持仓 (Portfolio对象)
    """
    lines = []

    lines.append("")
    lines.append("=" * 80)
    lines.append("交易建议")
    lines.append("=" * 80)
    lines.append("")

    # 卖出操作
    if sell_trades:
        lines.append(f"📉 卖出操作 ({len(sell_trades)})")
        lines.append("-" * 80)
        for i, trade in enumerate(sell_trades, 1):
            lines.append(f"  [{i}] {trade.ts_code}")
            lines.append(f"      操作: 卖出")
            lines.append(f"      价格: ¥{trade.price:.3f}")
            lines.append(f"      数量: {trade.shares} 股")
            lines.append(f"      预计收入: ¥{trade.amount:,.2f}")
            lines.append(f"      原因: {trade.reason}")
            lines.append("")

    # 买入操作
    if buy_trades:
        lines.append(f"📈 买入操作 ({len(buy_trades)})")
        lines.append("-" * 80)
        for i, trade in enumerate(buy_trades, 1):
            lines.append(f"  [{i}] {trade.ts_code}")
            lines.append(f"      操作: 买入")
            lines.append(f"      价格: ¥{trade.price:.3f}")
            lines.append(f"      数量: {trade.shares} 股")
            lines.append(f"      预计成本: ¥{abs(trade.amount):,.2f}")
            lines.append(f"      原因: {trade.reason}")
            lines.append("")

    if not sell_trades and not buy_trades:
        lines.append("✅ 无需交易")
        lines.append("-" * 80)
        lines.append("  当前持仓无需调整，继续持有即可。")
        lines.append("")

    # 交易后预期状态
    lines.append("📊 交易后预期状态")
    lines.append("-" * 80)

    expected_cash = portfolio.cash
    for trade in sell_trades:
        expected_cash += trade.amount
    for trade in buy_trades:
        expected_cash += trade.amount  # amount是负数

    expected_positions = portfolio.get_position_count() - len(sell_trades) + len(buy_trades)

    lines.append(f"  预期现金: ¥{expected_cash:,.2f}")
    lines.append(f"  预期持仓数: {expected_positions}")
    lines.append("")

    lines.append("=" * 80)

    print("\n".join(lines))


def print_execution_summary(existing_record: Dict, trade_date_display: str):
    """
    打印已执行交易的摘要

    Args:
        existing_record: 已存在的执行记录
        trade_date_display: 交易日期显示格式
    """
    print("")
    print("=" * 70)
    print(f"⚠️  今日（{trade_date_display}）已执行过交易")
    print("=" * 70)

    existing_trades = existing_record.get('trades', [])
    exec_time = existing_record.get('execution_time', existing_record.get('timestamp', '未知'))

    print(f"\n📋 执行时间: {exec_time}")
    print(f"📋 交易记录数: {existing_record.get('trade_count', len(existing_trades))} 笔\n")

    if existing_trades:
        print("📋 今日已执行交易明细：")
        for t in existing_trades:
            action_icon = "🔴 卖出" if t.get('action') == 'SELL' else "🟢 买入"
            shares = t.get('shares', 0)
            price = t.get('price', 0)
            amount = abs(t.get('amount', 0))
            print(f"   {action_icon} {t.get('ts_code', '未知')} × {shares}股 @ ¥{price:.3f} = ¥{amount:,.2f}")
    else:
        print("📋 今日已检查，无需交易（空交易日）")


def print_snapshot_info(snapshot_data: Dict):
    """
    打印快照信息

    Args:
        snapshot_data: 快照数据字典
    """
    snap_portfolio = snapshot_data.get('portfolio', {})
    snap_cash = snap_portfolio.get('cash', 0)
    snap_positions = snap_portfolio.get('positions', [])
    snap_total = snap_cash + sum(
        p.get('shares', 0) * p.get('entry_price', 0)
        for p in snap_positions
    )
    print(f"\n📊 当日快照持仓状态：")
    print(f"   现金: ¥{snap_cash:,.2f}")
    print(f"   持仓数: {len(snap_positions)} 只")
    print(f"   估算总值: ¥{snap_total:,.2f}")


def print_snapshot_list(snapshots: List[Dict], portfolio_name: str):
    """
    打印快照列表

    Args:
        snapshots: 快照列表
        portfolio_name: 持仓名称
    """
    print("=" * 80)
    print(f"📸 可用快照列表 ({portfolio_name})")
    print("=" * 80)

    if not snapshots:
        print("  (暂无快照)")
    else:
        print(f"{'日期':<12} {'时间':<20} {'类型':<12} {'现金':>15} {'持仓数':>8}")
        print("-" * 80)
        for s in snapshots:
            print(f"{s['date']:<12} {s['timestamp']:<20} {s['snapshot_type']:<12} "
                  f"¥{s['cash']:>12,.2f} {s['position_count']:>8}")

    print("=" * 80)
    print(f"共 {len(snapshots)} 个快照")


def print_restore_preview(restore_date: str, snapshot_data: Dict):
    """
    打印恢复预览

    Args:
        restore_date: 恢复日期
        snapshot_data: 快照数据
    """
    portfolio_preview = snapshot_data.get('portfolio', {})
    positions_preview = portfolio_preview.get('positions', [])

    print("=" * 80)
    print(f"📸 快照预览 (日期: {restore_date})")
    print("=" * 80)
    print(f"  快照时间: {snapshot_data.get('timestamp', '未知')}")
    print(f"  快照类型: {snapshot_data.get('snapshot_type', '未知')}")
    print(f"  可用现金: ¥{portfolio_preview.get('cash', 0):,.2f}")
    print(f"  持仓数量: {len(positions_preview)}")

    if positions_preview:
        print("")
        print("  持仓明细:")
        for pos in positions_preview:
            print(f"    - {pos['ts_code']}: {pos['shares']}股 @¥{pos['entry_price']:.3f}")

    print("=" * 80)


def print_data_info(generator):
    """
    打印数据信息

    Args:
        generator: SignalGenerator实例
    """
    print("=" * 80)
    print("📊 数据信息")
    print("=" * 80)
    if generator.latest_price_date:
        print(f"最新价格日期:  {generator.latest_price_date}")
    if generator.lookback_start_date:
        print(f"Lookback起始:  {generator.lookback_start_date}")
    print(f"Lookback周期:   {generator.lookback_days} 天")
    print("=" * 80)
    print("")
