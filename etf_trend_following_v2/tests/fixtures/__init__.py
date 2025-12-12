"""
Test fixtures module

Provides helper functions to load test fixture data.
"""

import pandas as pd
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent
DATA_DIR = FIXTURES_DIR / 'data'


def load_fixture_data(symbol: str) -> pd.DataFrame:
    """
    Load fixture OHLCV data for testing

    Args:
        symbol: ETF symbol (e.g., 'TEST_TREND_1.SH')

    Returns:
        DataFrame with OHLCV data in backtesting.py format
        (capitalized columns: Open, High, Low, Close, Volume)

    Raises:
        FileNotFoundError: If fixture file doesn't exist
    """
    file_path = DATA_DIR / f'{symbol}.csv'

    if not file_path.exists():
        raise FileNotFoundError(
            f"Fixture data not found: {file_path}\n"
            f"Run generate_test_data.py to create fixtures."
        )

    # Load CSV
    df = pd.read_csv(file_path, index_col=0)

    # Parse date column
    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    df = df.set_index('trade_date')
    df.index.name = 'date'

    # Rename columns to backtesting.py format (capitalized)
    df = df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    })

    # Select required columns
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

    return df


def get_fixture_symbols():
    """
    Get list of available fixture symbols

    Returns:
        List of symbol strings
    """
    if not DATA_DIR.exists():
        return []

    csv_files = list(DATA_DIR.glob('*.csv'))
    symbols = [f.stem for f in csv_files]

    return sorted(symbols)
