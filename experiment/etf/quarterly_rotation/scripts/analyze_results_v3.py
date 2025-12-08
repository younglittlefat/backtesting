"""
v3 结果分析脚本

功能:
1. 对比不同调仓周期的表现
2. 与v2基准对比
3. 生成分析报告
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

# 路径配置
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
RESULTS_V3_DIR = PROJECT_DIR / 'results' / 'comparison_v3'
RESULTS_V2_DIR = PROJECT_DIR / 'results' / 'comparison_v2'


def load_v3_results() -> Dict:
    """加载v3回测结果"""
    results = {}

    for period in ['quarterly', 'semi_annual', 'annual']:
        json_path = RESULTS_V3_DIR / f'v3_{period}_overall.json'
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                results[period] = json.load(f)

    return results


def load_v2_results() -> Dict:
    """加载v2回测结果作为基准"""
    results = {}

    # 轮动组
    rotation_path = RESULTS_V2_DIR / 'rotation_overall_v2.json'
    if rotation_path.exists():
        with open(rotation_path, 'r', encoding='utf-8') as f:
            results['v2_rotation'] = json.load(f)

    # 固定组
    static_path = RESULTS_V2_DIR / 'static_overall_v2.json'
    if static_path.exists():
        with open(static_path, 'r', encoding='utf-8') as f:
            results['v2_static'] = json.load(f)

    return results


def generate_comparison_table(v3_results: Dict, v2_results: Dict) -> pd.DataFrame:
    """生成对比表格"""
    rows = []

    # v3结果
    period_names = {
        'quarterly': 'v3-季度',
        'semi_annual': 'v3-半年',
        'annual': 'v3-年度'
    }

    for period, name in period_names.items():
        if period in v3_results:
            r = v3_results[period]
            rows.append({
                '方案': name,
                '总收益率(%)': r.get('total_return', 0),
                '年化收益(%)': r.get('annualized_return', 0),
                '夏普比率': r.get('sharpe', 0),
                '最大回撤(%)': r.get('max_drawdown', 0),
                '总交易': r.get('total_trades', 0),
                '调仓交易': r.get('rotation_trades', 0),
                '信号交易': r.get('signal_trades', 0),
                '总成本': r.get('total_cost', 0)
            })

    # v2基准
    if 'v2_rotation' in v2_results:
        r = v2_results['v2_rotation']
        rows.append({
            '方案': 'v2-轮动(无成本)',
            '总收益率(%)': r.get('total_return', 0),
            '年化收益(%)': r.get('annualized_return', 0),
            '夏普比率': r.get('sharpe', 0),
            '最大回撤(%)': r.get('max_drawdown', 0),
            '总交易': int(r.get('total_trades', 0)),
            '调仓交易': 0,
            '信号交易': int(r.get('total_trades', 0)),
            '总成本': 0
        })

    if 'v2_static' in v2_results:
        r = v2_results['v2_static']
        rows.append({
            '方案': '固定组',
            '总收益率(%)': r.get('total_return', 0),
            '年化收益(%)': r.get('annualized_return', 0),
            '夏普比率': r.get('sharpe', 0),
            '最大回撤(%)': r.get('max_drawdown', 0),
            '总交易': int(r.get('total_trades', 0)),
            '调仓交易': 0,
            '信号交易': int(r.get('total_trades', 0)),
            '总成本': 0
        })

    return pd.DataFrame(rows)


def analyze_rotation_cost(v3_results: Dict) -> Dict:
    """分析调仓成本"""
    analysis = {}

    for period, r in v3_results.items():
        rotation_cost = r.get('total_rotation_cost', 0)
        signal_cost = r.get('total_signal_cost', 0)
        total_cost = r.get('total_cost', 0)
        initial = r.get('initial_cash', 1_000_000)

        analysis[period] = {
            'rotation_cost': rotation_cost,
            'rotation_cost_pct': rotation_cost / initial * 100,
            'signal_cost': signal_cost,
            'signal_cost_pct': signal_cost / initial * 100,
            'total_cost': total_cost,
            'total_cost_pct': total_cost / initial * 100
        }

    return analysis


def generate_report(v3_results: Dict, v2_results: Dict) -> str:
    """生成Markdown分析报告"""
    comparison_df = generate_comparison_table(v3_results, v2_results)
    cost_analysis = analyze_rotation_cost(v3_results)

    report = f"""# 季度轮动实验 v3 分析报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 一、实验说明

v3版本实现了**真实调仓模拟**，相比v2的主要改进：
- 计算调仓交易成本（佣金+滑点）
- 新标的等待KAMA信号才建仓
- 重叠标的保持持仓不动

### 成本模型
- 买入成本: 0.025%佣金 + 0.1%滑点 = 0.125%
- 卖出成本: 0.025%佣金 + 0.1%滑点 = 0.125%

---

## 二、核心结论

{comparison_df.to_markdown(index=False)}

---

## 三、调仓成本分析

| 方案 | 调仓成本 | 占初始资金 | 信号成本 | 占初始资金 | 总成本 |
|------|-------:|----------:|-------:|----------:|------:|
"""

    for period, c in cost_analysis.items():
        period_name = {'quarterly': '季度', 'semi_annual': '半年', 'annual': '年度'}.get(period, period)
        report += f"| v3-{period_name} | {c['rotation_cost']:.2f} | {c['rotation_cost_pct']:.3f}% | {c['signal_cost']:.2f} | {c['signal_cost_pct']:.3f}% | {c['total_cost']:.2f} |\n"

    report += """
---

## 四、假设验证

"""
    # 检验假设
    if 'quarterly' in v3_results and 'v2_rotation' in v2_results:
        v3_quarterly = v3_results['quarterly']['total_return']
        v2_rotation = v2_results['v2_rotation']['total_return']
        diff = v3_quarterly - v2_rotation

        if diff < -1:
            h1_result = "✅ 通过"
            h1_note = f"v3收益 {v3_quarterly:.2f}% < v2收益 {v2_rotation:.2f}%，差值 {diff:.2f}%"
        else:
            h1_result = "❌ 未通过"
            h1_note = f"v3收益 {v3_quarterly:.2f}%，v2收益 {v2_rotation:.2f}%，差值 {diff:.2f}%（未达显著）"

        report += f"""| 假设 | 预期 | 实际结果 | 状态 |
|------|------|----------|:----:|
| H1: 调仓成本显著影响收益 | v3收益 < v2收益，差值 > 1% | {h1_note} | {h1_result} |
"""

    # H2: 低频调仓成本更低
    costs = {}
    for period in ['quarterly', 'semi_annual', 'annual']:
        if period in v3_results:
            costs[period] = v3_results[period].get('total_rotation_cost', 0)

    if len(costs) >= 2:
        if costs.get('annual', float('inf')) < costs.get('semi_annual', float('inf')) < costs.get('quarterly', 0):
            h2_result = "✅ 通过"
        else:
            h2_result = "❌ 未通过"

        report += f"| H2: 低频调仓成本更低 | 年度 < 半年 < 季度 | 季度:{costs.get('quarterly', 0):.0f}, 半年:{costs.get('semi_annual', 0):.0f}, 年度:{costs.get('annual', 0):.0f} | {h2_result} |\n"

    # H3: 存在最优调仓频率
    sharpes = {}
    for period in ['quarterly', 'semi_annual', 'annual']:
        if period in v3_results:
            sharpes[period] = v3_results[period].get('sharpe', 0)

    if sharpes:
        best_period = max(sharpes, key=sharpes.get)
        best_name = {'quarterly': '季度', 'semi_annual': '半年', 'annual': '年度'}.get(best_period, best_period)
        report += f"| H3: 存在最优调仓频率 | 夏普最大化 | 最优: {best_name} (夏普 {sharpes[best_period]:.4f}) | ✅ 识别 |\n"

    report += """
---

## 五、数据来源

- v3结果: `results/comparison_v3/`
- v2基准: `results/comparison_v2/`
- 调仓计划: `pool_rotation_schedule.json`

"""

    return report


def main():
    print("加载v3回测结果...")
    v3_results = load_v3_results()
    print(f"  找到 {len(v3_results)} 个v3结果")

    print("加载v2基准结果...")
    v2_results = load_v2_results()
    print(f"  找到 {len(v2_results)} 个v2结果")

    if not v3_results:
        print("\n错误: 未找到v3回测结果，请先运行 run_backtests_v3.py")
        sys.exit(1)

    # 生成对比表
    comparison_df = generate_comparison_table(v3_results, v2_results)
    print("\n=== 对比结果 ===")
    print(comparison_df.to_string(index=False))

    # 保存对比表
    comparison_path = RESULTS_V3_DIR / 'v3_comparison_table.csv'
    comparison_df.to_csv(comparison_path, index=False)
    print(f"\n已保存: {comparison_path}")

    # 生成报告
    report = generate_report(v3_results, v2_results)
    report_path = RESULTS_V3_DIR / 'V3_ANALYSIS_REPORT.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"已保存: {report_path}")

    print("\n分析完成!")


if __name__ == '__main__':
    main()
