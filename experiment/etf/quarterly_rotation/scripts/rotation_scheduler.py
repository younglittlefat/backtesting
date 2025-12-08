"""
调仓日历生成器 - 根据配置生成不同周期的调仓日期

支持的调仓周期:
- quarterly: 季度（1月/4月/7月/10月）
- semi-annual: 半年（1月/7月）
- annual: 年度（1月）
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd


class RotationScheduler:
    """调仓日历生成器"""

    # 周期定义
    PERIOD_MONTHS = {
        'quarterly': [1, 4, 7, 10],
        'semi-annual': [1, 7],
        'annual': [1]
    }

    def __init__(
        self,
        rotation_schedule_path: str,
        rotation_period: str = 'quarterly'
    ):
        """
        初始化调仓日历

        参数:
            rotation_schedule_path: pool_rotation_schedule.json路径
            rotation_period: 调仓周期 (quarterly/semi-annual/annual)
        """
        self.rotation_period = rotation_period
        self.schedule_path = Path(rotation_schedule_path)

        # 加载原始季度调仓计划
        with open(self.schedule_path, 'r', encoding='utf-8') as f:
            self.quarterly_schedule = json.load(f)

        # 根据周期重新组织调仓计划
        self.rotation_schedule = self._build_rotation_schedule()

    def _build_rotation_schedule(self) -> Dict[str, Dict]:
        """根据调仓周期构建调仓计划"""
        if self.rotation_period == 'quarterly':
            return self._build_quarterly_schedule()
        elif self.rotation_period == 'semi-annual':
            return self._build_semi_annual_schedule()
        elif self.rotation_period == 'annual':
            return self._build_annual_schedule()
        else:
            raise ValueError(f"不支持的调仓周期: {self.rotation_period}")

    def _build_quarterly_schedule(self) -> Dict[str, Dict]:
        """季度调仓：直接使用原始计划"""
        return self.quarterly_schedule.copy()

    def _build_semi_annual_schedule(self) -> Dict[str, Dict]:
        """半年调仓：合并相邻两个季度"""
        schedule = {}

        # 按年份分组
        quarters_by_year = {}
        for qtr, info in self.quarterly_schedule.items():
            year = qtr[:4]
            if year not in quarters_by_year:
                quarters_by_year[year] = {}
            quarters_by_year[year][qtr] = info

        for year, quarters in sorted(quarters_by_year.items()):
            qtrs = sorted(quarters.keys())

            # 上半年 (Q1-Q2) -> H1
            h1_qtrs = [q for q in qtrs if q.endswith('Q1') or q.endswith('Q2')]
            if h1_qtrs:
                h1_start_qtr = h1_qtrs[0]
                h1_end_qtr = h1_qtrs[-1]
                h1_key = f"{year}H1"

                # 使用上半年第一个季度的池子
                schedule[h1_key] = {
                    'start': quarters[h1_start_qtr]['start'],
                    'end': quarters[h1_end_qtr]['end'],
                    'etfs': quarters[h1_start_qtr]['etfs'],
                    'source_quarter': h1_start_qtr
                }

            # 下半年 (Q3-Q4) -> H2
            h2_qtrs = [q for q in qtrs if q.endswith('Q3') or q.endswith('Q4')]
            if h2_qtrs:
                h2_start_qtr = h2_qtrs[0]
                h2_end_qtr = h2_qtrs[-1]
                h2_key = f"{year}H2"

                schedule[h2_key] = {
                    'start': quarters[h2_start_qtr]['start'],
                    'end': quarters[h2_end_qtr]['end'],
                    'etfs': quarters[h2_start_qtr]['etfs'],
                    'source_quarter': h2_start_qtr
                }

        return schedule

    def _build_annual_schedule(self) -> Dict[str, Dict]:
        """年度调仓：使用每年第一季度的池子"""
        schedule = {}

        quarters_by_year = {}
        for qtr, info in self.quarterly_schedule.items():
            year = qtr[:4]
            if year not in quarters_by_year:
                quarters_by_year[year] = {}
            quarters_by_year[year][qtr] = info

        for year, quarters in sorted(quarters_by_year.items()):
            qtrs = sorted(quarters.keys())
            if not qtrs:
                continue

            first_qtr = qtrs[0]
            last_qtr = qtrs[-1]

            schedule[year] = {
                'start': quarters[first_qtr]['start'],
                'end': quarters[last_qtr]['end'],
                'etfs': quarters[first_qtr]['etfs'],
                'source_quarter': first_qtr
            }

        return schedule

    def get_rotation_dates(self, trading_calendar: List[str]) -> List[str]:
        """
        获取所有调仓日期

        参数:
            trading_calendar: 交易日历（YYYYMMDD格式的日期列表）

        返回:
            调仓日期列表
        """
        rotation_dates = []
        trading_set = set(trading_calendar)

        for period_key, info in self.rotation_schedule.items():
            start_date = info['start'].replace('-', '')

            # 找到该日期或之后的第一个交易日
            rotation_date = self._find_trading_day(start_date, trading_calendar)
            if rotation_date:
                rotation_dates.append(rotation_date)

        return sorted(set(rotation_dates))

    def _find_trading_day(
        self,
        target_date: str,
        trading_calendar: List[str],
        forward: bool = True
    ) -> Optional[str]:
        """找到目标日期当天或之后/之前的第一个交易日"""
        trading_set = set(trading_calendar)

        if target_date in trading_set:
            return target_date

        # 转换为datetime进行日期计算
        dt = datetime.strptime(target_date, '%Y%m%d')

        for i in range(30):  # 最多搜索30天
            if forward:
                check_dt = dt + timedelta(days=i)
            else:
                check_dt = dt - timedelta(days=i)

            check_date = check_dt.strftime('%Y%m%d')
            if check_date in trading_set:
                return check_date

        return None

    def get_pool_for_date(self, date: str) -> Tuple[str, List[str]]:
        """
        获取指定日期对应的ETF池

        参数:
            date: 日期（YYYYMMDD或YYYY-MM-DD格式）

        返回:
            (周期名称, ETF列表)
        """
        # 标准化日期格式
        if '-' in date:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
        else:
            date_obj = datetime.strptime(date, '%Y%m%d')

        # 遍历找到包含该日期的周期
        for period_key, info in self.rotation_schedule.items():
            start = datetime.strptime(info['start'], '%Y-%m-%d')
            end = datetime.strptime(info['end'], '%Y-%m-%d')

            if start <= date_obj <= end:
                return period_key, info['etfs']

        return None, []

    def get_all_etfs(self) -> List[str]:
        """获取所有周期涉及的ETF并集"""
        all_etfs = set()
        for info in self.rotation_schedule.values():
            all_etfs.update(info['etfs'])
        return sorted(list(all_etfs))

    def get_period_info(self) -> List[Dict]:
        """获取所有调仓周期信息"""
        periods = []
        for period_key in sorted(self.rotation_schedule.keys()):
            info = self.rotation_schedule[period_key]
            periods.append({
                'period': period_key,
                'start': info['start'],
                'end': info['end'],
                'etf_count': len(info['etfs']),
                'etfs': info['etfs']
            })
        return periods

    def summary(self) -> Dict:
        """获取调仓计划摘要"""
        all_etfs = self.get_all_etfs()
        periods = self.get_period_info()

        return {
            'rotation_period': self.rotation_period,
            'total_periods': len(periods),
            'total_unique_etfs': len(all_etfs),
            'periods': periods
        }


def load_trading_calendar(data_dir: str, start_date: str, end_date: str) -> List[str]:
    """
    从ETF数据文件中提取交易日历

    参数:
        data_dir: ETF数据目录
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)

    返回:
        交易日期列表
    """
    data_path = Path(data_dir)

    # 找一个有完整数据的ETF
    sample_files = list(data_path.glob('*.csv'))[:10]

    all_dates = set()
    for csv_file in sample_files:
        try:
            df = pd.read_csv(csv_file, usecols=['trade_date'])
            df['trade_date'] = df['trade_date'].astype(str)
            dates = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]['trade_date']
            all_dates.update(dates.tolist())
        except Exception:
            continue

    return sorted(list(all_dates))


if __name__ == '__main__':
    # 测试代码
    import sys

    schedule_path = Path(__file__).parent.parent / 'pool_rotation_schedule.json'

    for period in ['quarterly', 'semi-annual', 'annual']:
        scheduler = RotationScheduler(str(schedule_path), rotation_period=period)
        summary = scheduler.summary()

        print(f"\n=== {period.upper()} ===")
        print(f"总周期数: {summary['total_periods']}")
        print(f"涉及ETF总数: {summary['total_unique_etfs']}")

        for p in summary['periods']:
            print(f"  {p['period']}: {p['start']} ~ {p['end']}, {p['etf_count']}只ETF")
