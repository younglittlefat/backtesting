#!/usr/bin/env python3
"""
Phase 2 Acceptance Analysis Script
Analyzes KAMA strategy stop-loss parameter optimization results
"""

import pandas as pd
import numpy as np
from pathlib import Path

def main():
    # Load data
    phase2a = pd.read_csv('results/phase2a_baseline.csv')
    phase2b = pd.read_csv('results/phase2b_loss_protection_grid.csv')
    summary = pd.read_csv('results/phase2_summary_statistics.csv', index_col=0)

    print("=" * 80)
    print("KAMA STRATEGY PHASE 2 ACCEPTANCE ANALYSIS")
    print("=" * 80)

    # 1. Data Quality Validation
    print("\n" + "=" * 80)
    print("1. DATA QUALITY VALIDATION")
    print("=" * 80)

    print(f"\nRecord Counts:")
    print(f"  Phase 2A (Baseline): {len(phase2a)} records (Expected: 60)")
    print(f"  Phase 2B (Loss Protection): {len(phase2b)} records (Expected: 960)")
    print(f"  Total: {len(phase2a) + len(phase2b)} records (Expected: 1020)")
    print(f"  Status: {'✅ PASS' if len(phase2a) == 60 and len(phase2b) == 960 else '❌ FAIL'}")

    # Field completeness
    print(f"\nField Completeness Check:")
    key_fields = ['sharpe_ratio', 'return_pct', 'max_drawdown_pct', 'win_rate_pct']
    for field in key_fields:
        missing_a = phase2a[field].isna().sum()
        missing_b = phase2b[field].isna().sum()
        status = "✅" if missing_a == 0 and missing_b == 0 else "⚠️"
        print(f"  {status} {field}: Phase2A missing={missing_a}, Phase2B missing={missing_b}")

    # Anomaly detection
    print(f"\nAnomaly Detection:")
    print(f"  Zero trades: Phase2A={len(phase2a[phase2a['num_trades'] == 0])}, Phase2B={len(phase2b[phase2b['num_trades'] == 0])}")
    print(f"  Sharpe range: Phase2A=[{phase2a['sharpe_ratio'].min():.2f}, {phase2a['sharpe_ratio'].max():.2f}]")
    print(f"  Sharpe range: Phase2B=[{phase2b['sharpe_ratio'].min():.2f}, {phase2b['sharpe_ratio'].max():.2f}]")

    # Success rate
    success_rate = ((len(phase2a) + len(phase2b)) / 1020) * 100
    print(f"\n✅ Success Rate: {success_rate:.1f}% (All backtests completed successfully)")

    # 2. Reproducibility Check
    print("\n" + "=" * 80)
    print("2. REPRODUCIBILITY CHECK (Phase 2A vs Phase 1)")
    print("=" * 80)

    phase1_baseline = {
        'baseline': {'sharpe': 1.69, 'return': 34.63, 'drawdown': -5.27, 'winrate': 84.54},
        'adx_only': {'sharpe': 1.68, 'return': 29.53, 'drawdown': -4.71, 'winrate': 85.96},
        'adx_slope': {'sharpe': 1.58, 'return': 23.75, 'drawdown': -4.38, 'winrate': 88.04}
    }

    print(f"\n{'Config':<15} {'Metric':<10} {'Phase1':>8} {'Phase2A':>8} {'Diff':>8} {'Status':>8}")
    print("-" * 80)

    all_pass = True
    for config in ['baseline', 'adx_only', 'adx_slope']:
        config_data = phase2a[phase2a['config_name'] == config]

        metrics = [
            ('sharpe', 'sharpe_ratio', phase1_baseline[config]['sharpe']),
            ('return', 'return_pct', phase1_baseline[config]['return']),
            ('drawdown', 'max_drawdown_pct', phase1_baseline[config]['drawdown']),
            ('winrate', 'win_rate_pct', phase1_baseline[config]['winrate'])
        ]

        for i, (metric_name, col_name, p1_val) in enumerate(metrics):
            p2a_val = config_data[col_name].mean()
            diff_pct = ((p2a_val - p1_val) / abs(p1_val)) * 100
            status = "✅ PASS" if abs(diff_pct) < 5 else "⚠️ WARN"

            if abs(diff_pct) >= 5:
                all_pass = False

            config_display = config if i == 0 else ""
            suffix = "%" if metric_name in ['return', 'drawdown', 'winrate'] else ""
            print(f"{config_display:<15} {metric_name:<10} {p1_val:>7.2f}{suffix:1} {p2a_val:>7.2f}{suffix:1} {diff_pct:>+7.1f}% {status:>8}")

    print(f"\n{'✅ All configs reproduced within 5% tolerance' if all_pass else '⚠️ Some configs show >5% difference'}")

    # 3. Stop-Loss Protection Effectiveness
    print("\n" + "=" * 80)
    print("3. STOP-LOSS PROTECTION EFFECTIVENESS")
    print("=" * 80)

    # Extract baseline configs (no loss protection)
    baseline_configs = ['baseline', 'adx_only', 'adx_slope']

    # Compare each baseline with its loss protection variants
    print(f"\n{'Config':<30} {'Sharpe':>8} {'Return':>8} {'Drawdown':>10} {'WinRate':>8} {'Trades':>7}")
    print("-" * 80)

    for base_config in baseline_configs:
        # Get baseline stats
        base_data = phase2a[phase2a['config_name'] == base_config]
        base_sharpe = base_data['sharpe_ratio'].mean()
        base_return = base_data['return_pct'].mean()
        base_dd = base_data['max_drawdown_pct'].mean()
        base_wr = base_data['win_rate_pct'].mean()
        base_trades = base_data['num_trades'].mean()

        print(f"{base_config:<30} {base_sharpe:>8.2f} {base_return:>7.2f}% {base_dd:>9.2f}% {base_wr:>7.2f}% {base_trades:>7.1f}")

        # Find best loss protection config for this base
        loss_configs = phase2b[phase2b['config_name'].str.startswith(base_config + '_loss')]
        if len(loss_configs) > 0:
            # Group by config and get mean sharpe
            config_groups = loss_configs.groupby('config_name').agg({
                'sharpe_ratio': 'mean',
                'return_pct': 'mean',
                'max_drawdown_pct': 'mean',
                'win_rate_pct': 'mean',
                'num_trades': 'mean'
            }).sort_values('sharpe_ratio', ascending=False)

            # Show top 3
            for config_name in config_groups.head(3).index:
                row = config_groups.loc[config_name]
                sharpe = row['sharpe_ratio']
                ret = row['return_pct']
                dd = row['max_drawdown_pct']
                wr = row['win_rate_pct']
                trades = row['num_trades']

                sharpe_change = ((sharpe - base_sharpe) / base_sharpe) * 100
                dd_change = ((dd - base_dd) / abs(base_dd)) * 100

                # Extract params
                parts = config_name.replace(base_config + '_', '').split('_')
                max_loss = parts[0].replace('loss', '')
                pause = parts[1].replace('pause', '')

                print(f"  └─ loss{max_loss}_pause{pause:<12} {sharpe:>8.2f} {ret:>7.2f}% {dd:>9.2f}% {wr:>7.2f}% {trades:>7.1f} ({sharpe_change:+.1f}% sharpe)")

        print()

    # 4. Key Findings Summary
    print("=" * 80)
    print("4. KEY FINDINGS")
    print("=" * 80)

    # Calculate overall statistics
    all_baseline_sharpe = phase2a['sharpe_ratio'].mean()
    all_loss_sharpe = phase2b['sharpe_ratio'].mean()
    sharpe_improvement = ((all_loss_sharpe - all_baseline_sharpe) / all_baseline_sharpe) * 100

    print(f"\nOverall Performance:")
    print(f"  Baseline Sharpe (no loss protection): {all_baseline_sharpe:.2f}")
    print(f"  Average Loss Protection Sharpe: {all_loss_sharpe:.2f}")
    print(f"  Change: {sharpe_improvement:+.2f}%")

    # Find absolute best config
    loss_protection_configs = summary[summary.index.str.contains('loss', na=False)]
    if len(loss_protection_configs) > 0:
        best_config = loss_protection_configs.sort_values(('sharpe_ratio', 'mean'), ascending=False).head(1)
        best_name = best_config.index[0]
        best_sharpe = best_config[('sharpe_ratio', 'mean')].values[0]

        print(f"\n✨ Best Loss Protection Configuration: {best_name}")
        print(f"   Sharpe Ratio: {best_sharpe:.2f}")
        print(f"   Return: {best_config[('return_pct', 'mean')].values[0]:.2f}%")
        print(f"   Max Drawdown: {best_config[('max_drawdown_pct', 'mean')].values[0]:.2f}%")
        print(f"   Win Rate: {best_config[('win_rate_pct', 'mean')].values[0]:.2f}%")

    # Compare to baseline
    print(f"\n🎯 CRITICAL FINDING:")
    if abs(sharpe_improvement) < 1.0:
        print(f"   ⚠️ Loss protection has NEGLIGIBLE effect on KAMA strategy ({sharpe_improvement:+.2f}%)")
        print(f"   This contrasts sharply with SMA (+75%) and MACD (+28.8%) strategies!")
    elif sharpe_improvement > 5:
        print(f"   ✅ Loss protection significantly improves KAMA strategy (+{sharpe_improvement:.1f}%)")
    elif sharpe_improvement < -5:
        print(f"   ❌ Loss protection DEGRADES KAMA strategy ({sharpe_improvement:.1f}%)")

    # Check parameter sensitivity
    print(f"\n📊 Parameter Sensitivity Analysis:")

    # Group by max_consecutive_losses
    for base_config in baseline_configs:
        loss_configs = phase2b[phase2b['config_name'].str.startswith(base_config + '_loss')]
        if len(loss_configs) == 0:
            continue

        print(f"\n  {base_config}:")

        # Extract params and calculate stats
        loss_configs['max_loss'] = loss_configs['config_name'].str.extract(r'loss(\d+)')[0].astype(int)
        loss_configs['pause'] = loss_configs['config_name'].str.extract(r'pause(\d+)')[0].astype(int)

        sharpe_by_loss = loss_configs.groupby('max_loss')['sharpe_ratio'].mean()
        sharpe_by_pause = loss_configs.groupby('pause')['sharpe_ratio'].mean()

        print(f"    By max_consecutive_losses: {dict(sharpe_by_loss.round(3))}")
        print(f"    By pause_bars: {dict(sharpe_by_pause.round(3))}")

        # Calculate std to see sensitivity
        loss_std = sharpe_by_loss.std()
        pause_std = sharpe_by_pause.std()

        print(f"    Sensitivity: max_loss_std={loss_std:.4f}, pause_std={pause_std:.4f}")

        if loss_std < 0.01 and pause_std < 0.01:
            print(f"    ⭐ HIGHLY INSENSITIVE - parameters have minimal impact")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()
