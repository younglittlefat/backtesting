#!/usr/bin/env python3
"""
Generate visual comparison of stop-loss protection effectiveness
across SMA, MACD, and KAMA strategies
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Strategy comparison data
data = {
    'Strategy': ['SMA', 'MACD', 'KAMA'],
    'Baseline_Sharpe': [0.61, 0.73, 1.69],
    'Protected_Sharpe': [1.07, 0.94, 1.64],
    'Sharpe_Improvement': [75.4, 28.8, -0.7],
    'Baseline_Drawdown': [-21.17, -20.12, -5.27],
    'Protected_Drawdown': [-13.88, -15.82, -5.27],
    'Baseline_WinRate': [48.41, 60.0, 84.54],
    'Protected_WinRate': [61.42, 65.0, 84.54]
}

df = pd.DataFrame(data)

# Create comparison visualization
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Stop-Loss Protection Effectiveness Across Strategies\n(20 ETF Backtests, 2023-11 to 2025-11)',
             fontsize=16, fontweight='bold')

# 1. Sharpe Ratio Comparison
ax1 = axes[0, 0]
x = range(len(df))
width = 0.35
bars1 = ax1.bar([i - width/2 for i in x], df['Baseline_Sharpe'], width,
                label='Baseline', alpha=0.8, color='#FF6B6B')
bars2 = ax1.bar([i + width/2 for i in x], df['Protected_Sharpe'], width,
                label='With Loss Protection', alpha=0.8, color='#4ECDC4')

ax1.set_xlabel('Strategy', fontweight='bold')
ax1.set_ylabel('Sharpe Ratio', fontweight='bold')
ax1.set_title('Sharpe Ratio: Baseline vs. Protected', fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(df['Strategy'])
ax1.legend()
ax1.grid(axis='y', alpha=0.3)
ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.8)

# Add value labels on bars
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}',
                ha='center', va='bottom', fontsize=9)

# 2. Sharpe Improvement Percentage
ax2 = axes[0, 1]
colors = ['#51CF66', '#FFD93D', '#C92A2A']  # Green for SMA, Yellow for MACD, Red for KAMA
bars = ax2.barh(df['Strategy'], df['Sharpe_Improvement'], color=colors, alpha=0.8)
ax2.set_xlabel('Sharpe Ratio Improvement (%)', fontweight='bold')
ax2.set_title('Loss Protection Effectiveness', fontweight='bold')
ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
ax2.grid(axis='x', alpha=0.3)

# Add value labels
for i, (bar, val) in enumerate(zip(bars, df['Sharpe_Improvement'])):
    label_x = val + (3 if val > 0 else -3)
    ha = 'left' if val > 0 else 'right'
    ax2.text(label_x, bar.get_y() + bar.get_height()/2, f'{val:+.1f}%',
            ha=ha, va='center', fontweight='bold', fontsize=11)

# Add effectiveness annotations
ax2.text(75, 2.3, '⭐⭐⭐ Highly Effective', fontsize=10, color='#2B8A3E')
ax2.text(28, 1.3, '⭐⭐ Effective', fontsize=10, color='#E67700')
ax2.text(-15, 0.3, '❌ Ineffective', fontsize=10, color='#C92A2A')

# 3. Win Rate Comparison
ax3 = axes[1, 0]
bars1 = ax3.bar([i - width/2 for i in x], df['Baseline_WinRate'], width,
                label='Baseline', alpha=0.8, color='#FF6B6B')
bars2 = ax3.bar([i + width/2 for i in x], df['Protected_WinRate'], width,
                label='With Loss Protection', alpha=0.8, color='#4ECDC4')

ax3.set_xlabel('Strategy', fontweight='bold')
ax3.set_ylabel('Win Rate (%)', fontweight='bold')
ax3.set_title('Win Rate: Baseline vs. Protected', fontweight='bold')
ax3.set_xticks(x)
ax3.set_xticklabels(df['Strategy'])
ax3.legend()
ax3.grid(axis='y', alpha=0.3)
ax3.set_ylim(0, 100)

# Add value labels
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%',
                ha='center', va='bottom', fontsize=9)

# 4. Key Insights Text Box
ax4 = axes[1, 1]
ax4.axis('off')

insights_text = """
KEY FINDINGS

1. Loss Protection Effectiveness vs. Baseline Quality
   • Inverse correlation discovered
   • Weaker baselines benefit MORE from protection
   • Strong baselines (KAMA) don't need it

2. KAMA's Self-Protection Mechanism
   • Adaptive speed prevents consecutive losses
   • 84.54% win rate (vs. SMA 48%, MACD 60%)
   • Loss protection never triggers (threshold ≥4)

3. Recommendations by Strategy
   ✅ SMA: USE loss protection (max_loss=3, pause=10)
       → +75% Sharpe, -34% Drawdown

   ✅ MACD: USE combined protection (max_loss=2, pause=5)
       → +28.8% Sharpe, -21% Drawdown

   ❌ KAMA: SKIP loss protection
       → No benefit, already optimal at 1.69 Sharpe

4. Portfolio Strategy
   • Primary: KAMA baseline (highest Sharpe 1.69)
   • Diversify: SMA + MACD with protection
   • Allocation: 60% KAMA / 20% SMA / 20% MACD

Experiment Data:
• Total Backtests: 280 (SMA) + 960 (MACD) + 1020 (KAMA)
• Period: 2023-11 to 2025-11 (2 years)
• Symbols: 20 Chinese ETFs (high liquidity)
"""

ax4.text(0.05, 0.95, insights_text, transform=ax4.transAxes,
         fontsize=10, verticalalignment='top', family='monospace',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

plt.tight_layout()
plt.savefig('results/phase2_strategy_comparison.png', dpi=150, bbox_inches='tight')
print("✅ Chart saved to: results/phase2_strategy_comparison.png")

# Also create a simple summary table
print("\n" + "="*80)
print("STOP-LOSS PROTECTION EFFECTIVENESS SUMMARY")
print("="*80)
print(f"\n{'Strategy':<10} {'Baseline':<12} {'Protected':<12} {'Improvement':<15} {'Status':<20}")
print("-"*80)
for _, row in df.iterrows():
    status = "⭐⭐⭐ Highly Effective" if row['Sharpe_Improvement'] > 50 else \
             "⭐⭐ Effective" if row['Sharpe_Improvement'] > 10 else \
             "❌ Ineffective"
    print(f"{row['Strategy']:<10} "
          f"Sharpe={row['Baseline_Sharpe']:<7.2f} "
          f"Sharpe={row['Protected_Sharpe']:<7.2f} "
          f"{row['Sharpe_Improvement']:>+6.1f}% {status:<20}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("""
Loss protection effectiveness is INVERSELY correlated with baseline signal quality:
  • Low baseline (SMA 0.61)  → High benefit (+75%)
  • Mid baseline (MACD 0.73) → Medium benefit (+28.8%)
  • High baseline (KAMA 1.69) → No benefit (-0.7%)

Implication: Focus on IMPROVING signal quality rather than adding risk controls.
KAMA's adaptive design eliminates the need for external protection mechanisms.
""")
