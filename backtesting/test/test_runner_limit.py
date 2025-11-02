import sys
from pathlib import Path

import numpy as np
import pandas as pd
import backtest_runner


def _write_dummy_csv(path: Path, start_price: float) -> None:
    dates = pd.date_range("2020-01-01", periods=120, freq="D")
    trend = np.linspace(start_price, start_price * 1.1, len(dates))
    oscillation = np.sin(np.linspace(0, 12, len(dates))) * start_price * 0.05
    close_series = pd.Series(trend + oscillation)
    open_price = close_series * 0.999
    high = pd.concat([open_price, close_series], axis=1).max(axis=1) * 1.001
    low = pd.concat([open_price, close_series], axis=1).min(axis=1) * 0.999
    pre_close = close_series.shift(1).fillna(close_series.iloc[0])
    change = close_series - pre_close
    pct_chg = np.where(pre_close != 0, change / pre_close, 0.0)
    volume = np.full(len(dates), 10000)
    amount = close_series * volume

    df = pd.DataFrame(
        {
            "trade_date": [d.strftime("%Y%m%d") for d in dates],
            "open": open_price,
            "high": high,
            "low": low,
            "close": close_series,
            "pre_close": pre_close,
            "change": change,
            "pct_chg": pct_chg,
            "volume": volume,
            "amount": amount,
        }
    )
    df.to_csv(path, index=False)


def test_instrument_limit_applies(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "out"
    csv_dir = data_dir / "daily" / "etf"
    csv_dir.mkdir(parents=True)
    _write_dummy_csv(csv_dir / "AAA.SZ.csv", 1.0)
    _write_dummy_csv(csv_dir / "BBB.SZ.csv", 2.0)

    argv = [
        "backtest_runner.py",
        "--data-dir",
        str(data_dir),
        "--output-dir",
        str(output_dir),
        "--stock",
        "AAA.SZ,BBB.SZ",
        "--instrument-limit",
        "1",
        "--disable-low-vol-filter",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    exit_code = backtest_runner.main()

    assert exit_code == 0
    stats_dir = output_dir / "etf" / "stats"
    stats_files = sorted(
        p for p in stats_dir.glob("*.csv") if not p.name.endswith("_trades.csv")
    )
    assert len(stats_files) == 1
    assert stats_files[0].name.startswith("AAA.SZ")
