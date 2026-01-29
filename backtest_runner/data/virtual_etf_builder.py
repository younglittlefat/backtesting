#!/usr/bin/env python3
"""
虚拟ETF数据生成器

将动态轮动的ETF池合并为单一虚拟ETF的OHLCV数据，用于backtesting.py框架回测。

核心功能：
1. 等权组合：每个轮动期内的N只ETF按1/N权重合成虚拟ETF
2. 轮动成本计入：在轮动日精确计算并扣除换仓成本
3. 数据对齐：处理不同ETF交易日不一致的情况（停牌、新上市）
4. 无未来数据泄露：严格按照时间顺序处理数据

技术方案：
- 输入：rotation_schedule.json（预计算的轮动表）
- 输出：虚拟ETF的OHLCV DataFrame（可直接用于backtesting.py）
- 等权组合方法：虚拟ETF价格 = Σ(单ETF价格 × 1/N) / 基准价格

使用示例：
    builder = VirtualETFBuilder(
        rotation_schedule_path='results/rotation_schedules/rotation_30d.json',
        data_dir='data/chinese_etf'
    )

    virtual_etf_data = builder.build(
        rebalance_mode=RebalanceMode.FULL_LIQUIDATION,
        trading_cost_pct=0.003  # 0.3%双边成本
    )

    # 直接用于backtesting.py
    bt = Backtest(virtual_etf_data, MyStrategy, cash=100000)
"""

import json
import warnings
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from etf_selector.data_loader import ETFDataLoader


class RebalanceMode(Enum):
    """再平衡模式"""
    FULL_LIQUIDATION = "full_liquidation"  # 全平仓：卖出所有旧持仓，买入新池子
    INCREMENTAL = "incremental"  # 增量调整：只调整变化的部分


@dataclass
class RotationSchedule:
    """轮动表数据结构"""
    metadata: Dict
    schedule: Dict[str, List[str]]  # {rotation_date: [etf_codes]}
    statistics: Optional[Dict] = None

    @classmethod
    def load(cls, json_path: str) -> 'RotationSchedule':
        """从JSON文件加载轮动表"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return cls(
            metadata=data['metadata'],
            schedule=data['schedule'],
            statistics=data.get('statistics')
        )


class VirtualETFBuilder:
    """虚拟ETF数据生成器"""

    def __init__(
        self,
        rotation_schedule_path: str,
        data_dir: str = 'data/chinese_etf'
    ):
        """初始化虚拟ETF数据生成器

        Args:
            rotation_schedule_path: 轮动表JSON文件路径
            data_dir: ETF数据根目录
        """
        self.rotation_schedule = RotationSchedule.load(rotation_schedule_path)
        self.data_loader = ETFDataLoader(data_dir)

        # 提取时间范围
        self.start_date = self.rotation_schedule.metadata['start_date']
        self.end_date = self.rotation_schedule.metadata['end_date']

        # 获取所有需要加载的ETF代码（去重）
        all_etf_codes = set()
        for etf_list in self.rotation_schedule.schedule.values():
            all_etf_codes.update(etf_list)
        self.all_etf_codes = sorted(all_etf_codes)

        print(f"[VirtualETFBuilder] 初始化完成:")
        print(f"  - 时间范围: {self.start_date} ~ {self.end_date}")
        print(f"  - 轮动次数: {self.rotation_schedule.metadata['total_rotations']}")
        print(f"  - 需加载ETF数量: {len(self.all_etf_codes)}")

    def build(
        self,
        rebalance_mode: RebalanceMode = RebalanceMode.FULL_LIQUIDATION,
        trading_cost_pct: float = 0.003,
        base_price: float = 1000.0,
        verbose: bool = True
    ) -> pd.DataFrame:
        """构建虚拟ETF数据

        Args:
            rebalance_mode: 再平衡模式
            trading_cost_pct: 交易成本比例（单边），默认0.3%
            base_price: 虚拟ETF初始价格，默认1000.0
            verbose: 是否显示详细信息

        Returns:
            虚拟ETF的OHLCV DataFrame，索引为日期，包含字段：
            - Open, High, Low, Close, Volume
            - rebalance_cost: 轮动成本（仅在轮动日有值）
            - active_etf_count: 当前池子中有效ETF数量
        """
        if verbose:
            print(f"\n[VirtualETFBuilder] 开始构建虚拟ETF数据")
            print(f"  - 再平衡模式: {rebalance_mode.value}")
            print(f"  - 交易成本: {trading_cost_pct*100:.2f}%")

        # Step 1: 加载所有ETF数据
        etf_data_dict = self._load_all_etf_data(verbose=verbose)

        # Step 2: 构建虚拟ETF价格序列（逐期归一化，包含成本计算）
        virtual_etf_df = self._build_virtual_etf_series(
            etf_data_dict,
            rebalance_mode=rebalance_mode,
            trading_cost_pct=trading_cost_pct,
            base_price=base_price,
            verbose=verbose
        )

        if verbose:
            print(f"\n[VirtualETFBuilder] 虚拟ETF数据构建完成")
            print(f"  - 总交易日: {len(virtual_etf_df)}")
            print(f"  - 初始价格: {virtual_etf_df['Close'].iloc[0]:.2f}")
            print(f"  - 最终价格: {virtual_etf_df['Close'].iloc[-1]:.2f}")
            print(f"  - 总收益率: {(virtual_etf_df['Close'].iloc[-1]/virtual_etf_df['Close'].iloc[0]-1)*100:.2f}%")

        return virtual_etf_df

    def _load_all_etf_data(
        self,
        verbose: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """加载所有需要的ETF数据

        Returns:
            {etf_code: DataFrame} 字典，DataFrame包含adj_close等字段
        """
        if verbose:
            print(f"\n[Step 1/3] 加载ETF数据...")

        etf_data_dict = {}
        failed_codes = []

        for i, etf_code in enumerate(self.all_etf_codes, 1):
            try:
                df = self.data_loader.load_etf_daily(
                    ts_code=etf_code,
                    start_date=self.start_date,
                    end_date=self.end_date,
                    use_adj=True
                )

                # 确保索引为日期类型
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)

                # 检查数据质量
                if len(df) < 10:
                    warnings.warn(f"ETF {etf_code} 数据不足10天，跳过")
                    failed_codes.append(etf_code)
                    continue

                # 检查复权价格列
                if 'adj_close' not in df.columns:
                    warnings.warn(f"ETF {etf_code} 缺少adj_close列，跳过")
                    failed_codes.append(etf_code)
                    continue

                etf_data_dict[etf_code] = df

                if verbose and i % 10 == 0:
                    print(f"  已加载 {i}/{len(self.all_etf_codes)} 只ETF")

            except FileNotFoundError:
                warnings.warn(f"ETF {etf_code} 数据文件不存在，跳过")
                failed_codes.append(etf_code)
            except Exception as e:
                warnings.warn(f"加载ETF {etf_code} 数据失败: {e}")
                failed_codes.append(etf_code)

        if verbose:
            print(f"  成功加载: {len(etf_data_dict)}/{len(self.all_etf_codes)} 只ETF")
            if failed_codes:
                print(f"  失败: {len(failed_codes)} 只 - {failed_codes[:5]}{'...' if len(failed_codes) > 5 else ''}")

        return etf_data_dict

    def _build_virtual_etf_series(
        self,
        etf_data_dict: Dict[str, pd.DataFrame],
        rebalance_mode: RebalanceMode,
        trading_cost_pct: float,
        base_price: float = 1000.0,
        verbose: bool = True
    ) -> pd.DataFrame:
        """构建虚拟ETF价格序列（逐期归一化，保证价格连续性）

        Args:
            etf_data_dict: ETF数据字典
            rebalance_mode: 再平衡模式
            trading_cost_pct: 交易成本比例（单边）
            base_price: 虚拟ETF初始价格
            verbose: 是否显示详细信息

        Returns:
            虚拟ETF的OHLCV DataFrame，包含rebalance_cost字段
        """
        if verbose:
            print(f"\n[Step 2/3] 构建虚拟ETF价格序列（逐期归一化）...")

        # 获取完整的交易日历（所有ETF的并集）
        all_dates = set()
        for df in etf_data_dict.values():
            all_dates.update(df.index)
        trading_calendar = sorted(all_dates)

        if verbose:
            print(f"  - 交易日历: {len(trading_calendar)} 天")

        # 初始化结果DataFrame
        result = pd.DataFrame(index=trading_calendar)
        result['Open'] = np.nan
        result['High'] = np.nan
        result['Low'] = np.nan
        result['Close'] = np.nan
        result['Volume'] = 0.0
        result['active_etf_count'] = 0
        result['rebalance_cost'] = 0.0

        # 按轮动期计算价格（逐期归一化）
        rotation_dates = sorted(self.rotation_schedule.schedule.keys())
        prev_close = base_price  # 前一期的结束价格（或初始资金）
        total_cost = 0.0

        for i, rotation_date in enumerate(rotation_dates):
            # 确定当前轮动期的时间范围
            period_start = pd.to_datetime(rotation_date)
            period_end = pd.to_datetime(rotation_dates[i+1]) if i < len(rotation_dates)-1 else pd.to_datetime(self.end_date)

            # 当前池子的ETF代码
            pool_codes = self.rotation_schedule.schedule[rotation_date]
            available_codes = [code for code in pool_codes if code in etf_data_dict]

            if not available_codes:
                warnings.warn(f"轮动期 {rotation_date} 无可用ETF数据，跳过")
                continue

            # 获取当前期内的交易日
            period_dates = [d for d in trading_calendar if period_start <= d < period_end]

            if not period_dates:
                continue

            # 计算轮动成本
            if i == 0:
                # 第一次买入：单边成本
                cost_pct = trading_cost_pct
            else:
                # 后续轮动：计算换手率
                prev_pool = set(self.rotation_schedule.schedule[rotation_dates[i-1]])
                curr_pool = set(pool_codes)

                if rebalance_mode == RebalanceMode.FULL_LIQUIDATION:
                    # 全平仓：双边成本
                    cost_pct = 2 * trading_cost_pct
                else:
                    # 增量调整：基于换手率
                    removed = len(prev_pool - curr_pool)
                    added = len(curr_pool - prev_pool)
                    turnover_ratio = (removed + added) / (2 * len(curr_pool))
                    cost_pct = 2 * turnover_ratio * trading_cost_pct

            # 记录轮动成本
            result.loc[period_start, 'rebalance_cost'] = cost_pct
            total_cost += cost_pct

            # 扣除成本后的可用资金
            adjusted_prev_close = prev_close * (1 - cost_pct)

            # 计算当前期的原始等权价格
            raw_prices = self._calculate_raw_equal_weight_prices(
                etf_data_dict,
                available_codes,
                period_dates
            )

            if raw_prices.empty or raw_prices['Close'].isna().all():
                warnings.warn(f"轮动期 {rotation_date} 无有效价格数据，跳过")
                continue

            # 计算归一化因子：将当前期的第一天价格归一化到adjusted_prev_close
            first_valid_idx = raw_prices['Close'].first_valid_index()
            if first_valid_idx is None:
                continue

            scale = adjusted_prev_close / raw_prices.loc[first_valid_idx, 'Close']

            # 应用归一化因子到当前期的所有价格
            for date in period_dates:
                if date in raw_prices.index:
                    for col in ['Open', 'High', 'Low', 'Close']:
                        if pd.notna(raw_prices.loc[date, col]):
                            result.loc[date, col] = raw_prices.loc[date, col] * scale
                    result.loc[date, 'Volume'] = raw_prices.loc[date, 'Volume']
                    result.loc[date, 'active_etf_count'] = raw_prices.loc[date, 'active_etf_count']

            # 更新prev_close为当前期的最后一天收盘价
            last_valid_date = max([d for d in period_dates if d in result.index and pd.notna(result.loc[d, 'Close'])])
            prev_close = result.loc[last_valid_date, 'Close']

            if verbose and i < 3:
                print(f"  - 轮动期 {i+1}: {rotation_date} ~ {period_end.date()}")
                print(f"    ETF数: {len(available_codes)}, 交易日: {len(period_dates)}, 成本: {cost_pct*100:.2f}%")
                print(f"    期初价格: {adjusted_prev_close:.2f}, 期末价格: {prev_close:.2f}")

        # 去除NaN行
        result = result.dropna(subset=['Close'])

        if verbose:
            print(f"  - 有效交易日: {len(result)} 天")
            print(f"  - 累计成本: {total_cost*100:.2f}%")

        return result

    def _calculate_raw_equal_weight_prices(
        self,
        etf_data_dict: Dict[str, pd.DataFrame],
        pool_codes: List[str],
        period_dates: List[pd.Timestamp]
    ) -> pd.DataFrame:
        """计算原始等权组合价格（未归一化）

        Args:
            etf_data_dict: ETF数据字典
            pool_codes: 当前池子的ETF代码列表
            period_dates: 当前轮动期的交易日列表

        Returns:
            原始等权价格DataFrame
        """
        result = pd.DataFrame(index=period_dates)
        result['Open'] = np.nan
        result['High'] = np.nan
        result['Low'] = np.nan
        result['Close'] = np.nan
        result['Volume'] = 0.0
        result['active_etf_count'] = 0

        for date in period_dates:
            # 收集当天有数据的ETF
            daily_prices = []
            daily_volumes = []

            for code in pool_codes:
                etf_df = etf_data_dict[code]
                if date in etf_df.index:
                    row = etf_df.loc[date]

                    # 处理重复索引情况：如果返回DataFrame，取第一行
                    if isinstance(row, pd.DataFrame):
                        if len(row) > 0:
                            row = row.iloc[0]
                        else:
                            continue

                    # 使用复权价格
                    adj_close = row.get('adj_close')
                    if pd.notna(adj_close):
                        daily_prices.append({
                            'open': row.get('adj_open', adj_close),
                            'high': row.get('adj_high', adj_close),
                            'low': row.get('adj_low', adj_close),
                            'close': adj_close
                        })
                        daily_volumes.append(row.get('volume', 0))

            if not daily_prices:
                continue

            # 等权平均
            n = len(daily_prices)
            result.loc[date, 'Open'] = sum(p['open'] for p in daily_prices) / n
            result.loc[date, 'High'] = sum(p['high'] for p in daily_prices) / n
            result.loc[date, 'Low'] = sum(p['low'] for p in daily_prices) / n
            result.loc[date, 'Close'] = sum(p['close'] for p in daily_prices) / n
            result.loc[date, 'Volume'] = sum(daily_volumes)
            result.loc[date, 'active_etf_count'] = n

        return result


def main():
    """命令行工具入口"""
    import argparse

    parser = argparse.ArgumentParser(description='生成虚拟ETF数据')
    parser.add_argument(
        '--rotation-schedule', type=str, required=True,
        help='轮动表JSON文件路径'
    )
    parser.add_argument(
        '--data-dir', type=str, default='data/chinese_etf',
        help='ETF数据根目录'
    )
    parser.add_argument(
        '--output', type=str, required=True,
        help='输出CSV文件路径'
    )
    parser.add_argument(
        '--rebalance-mode', type=str, default='full_liquidation',
        choices=['full_liquidation', 'incremental'],
        help='再平衡模式'
    )
    parser.add_argument(
        '--trading-cost', type=float, default=0.003,
        help='交易成本比例（单边），默认0.003（0.3%）'
    )

    args = parser.parse_args()

    # 构建虚拟ETF
    builder = VirtualETFBuilder(
        rotation_schedule_path=args.rotation_schedule,
        data_dir=args.data_dir
    )

    rebalance_mode = RebalanceMode(args.rebalance_mode)
    virtual_etf_df = builder.build(
        rebalance_mode=rebalance_mode,
        trading_cost_pct=args.trading_cost,
        verbose=True
    )

    # 保存数据
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    virtual_etf_df.to_csv(output_path)

    print(f"\n虚拟ETF数据已保存到: {output_path}")
    print(f"数据形状: {virtual_etf_df.shape}")
    print("\n前5行:")
    print(virtual_etf_df.head())


if __name__ == '__main__':
    main()
