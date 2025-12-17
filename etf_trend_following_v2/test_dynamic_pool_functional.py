"""
Functional test for dynamic pool filtering on real ETF data.
Tests dynamic pool size on 2024-01-02 and 2022-01-04.
"""

import sys
sys.path.insert(0, '/mnt/d/git/backtesting')

from etf_trend_following_v2.src.data_loader import scan_all_etfs, filter_by_dynamic_liquidity

# Test parameters (balanced configuration as specified)
MIN_AVG_AMOUNT = 5_000_000  # 5M yuan (MA5)
MIN_AVG_VOLUME = 500_000    # 500k shares (MA5)
MIN_LISTING_DAYS = 60       # 60 days minimum listing
DATA_DIR = '/mnt/d/git/backtesting/data/chinese_etf/daily'

def test_dynamic_pool_on_date(test_date: str):
    """Test dynamic pool filtering on a specific date"""
    print(f"\n{'='*60}")
    print(f"Testing Dynamic Pool Filtering on {test_date}")
    print(f"{'='*60}")

    # Scan all ETFs
    print("\n1. Scanning all ETF files...")
    all_symbols = scan_all_etfs(DATA_DIR)
    print(f"   Found {len(all_symbols)} ETF symbols in data directory")

    # Apply dynamic filtering
    print("\n2. Applying dynamic liquidity filter...")
    print(f"   - min_avg_amount: {MIN_AVG_AMOUNT:,} yuan (MA5)")
    print(f"   - min_avg_volume: {MIN_AVG_VOLUME:,} shares (MA5)")
    print(f"   - min_listing_days: {MIN_LISTING_DAYS} days")

    # Note: TuShare data uses hands (1 hand = 100 shares) and k_yuan (1 unit = 1000 yuan)
    # So we need to scale thresholds accordingly
    passed_symbols = filter_by_dynamic_liquidity(
        symbols=all_symbols,
        data_dir=DATA_DIR,
        as_of_date=test_date,
        min_amount=MIN_AVG_AMOUNT / 1000,  # Convert to k_yuan
        min_volume=MIN_AVG_VOLUME / 100,    # Convert to hands
        lookback_days=5,  # MA5
        min_listing_days=MIN_LISTING_DAYS,
        use_adj=True
    )

    print(f"\n3. Results:")
    print(f"   - Total ETFs scanned: {len(all_symbols)}")
    print(f"   - ETFs passing filter: {len(passed_symbols)}")
    print(f"   - Pass rate: {len(passed_symbols)/len(all_symbols)*100:.1f}%")

    # Show sample of passed symbols
    print(f"\n4. Sample of passed symbols (first 10):")
    for i, symbol in enumerate(sorted(passed_symbols)[:10]):
        print(f"   {i+1}. {symbol}")

    return len(all_symbols), len(passed_symbols)

if __name__ == '__main__':
    # Test on 2024-01-02 (recent date)
    total_2024, passed_2024 = test_dynamic_pool_on_date('2024-01-02')

    # Test on 2022-01-04 (earlier date)
    total_2022, passed_2022 = test_dynamic_pool_on_date('2022-01-04')

    # Summary comparison
    print(f"\n{'='*60}")
    print("Summary Comparison")
    print(f"{'='*60}")
    print(f"2024-01-02: {passed_2024}/{total_2024} ETFs passed ({passed_2024/total_2024*100:.1f}%)")
    print(f"2022-01-04: {passed_2022}/{total_2022} ETFs passed ({passed_2022/total_2022*100:.1f}%)")
    print(f"\nDifference: {passed_2024 - passed_2022:+d} ETFs")
    print("\nExpected behavior:")
    print("- 2024 should have MORE passing ETFs (market growth + new ETFs)")
    print("- 2022 should have FEWER passing ETFs (fewer ETFs existed)")

    # Validate expectations
    if passed_2024 > passed_2022:
        print("\n✓ PASS: 2024 has more passing ETFs than 2022 (expected)")
    else:
        print("\n✗ FAIL: 2022 has more passing ETFs than 2024 (unexpected)")

    # Check if reasonable range
    if 200 <= passed_2024 <= 500:
        print(f"✓ PASS: 2024 pool size ({passed_2024}) is in reasonable range (200-500)")
    else:
        print(f"⚠ WARNING: 2024 pool size ({passed_2024}) is outside expected range (200-500)")
