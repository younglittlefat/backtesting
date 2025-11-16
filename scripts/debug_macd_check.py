#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick MACD Double-Check

Reads per-instrument CSVs (with adj_* columns supported), computes MACD(12,26,9)
by default (or from config/macd_strategy_params.json), and prints the last N rows
for visual inspection, including whether a cross happened on the final bar.

Usage:
  python scripts/debug_macd_check.py \
    --tickers 561160.SH 510210.SH \
    --data-dir data/chinese_etf/daily \
    --end-date 2025-11-14 \
    --rows 6
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple

import pandas as pd

# Local imports
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from utils.data_loader import load_chinese_ohlcv_data
from strategies.macd_cross import MACD  # use exact same implementation as strategy


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compute MACD for given tickers and print last rows.")
    p.add_argument("--tickers", nargs="+", required=True, help="List of ts_codes, e.g. 561160.SH 510210.SH")
    p.add_argument("--data-dir", default="data/chinese_etf/daily", help="Root data dir (supports /etf subdir)")
    p.add_argument("--end-date", default=None, help="YYYY-MM-DD or YYYYMMDD; defaults to latest in CSV")
    p.add_argument("--rows", type=int, default=6, help="How many trailing rows to print")
    p.add_argument("--config", default="config/macd_strategy_params.json", help="Params JSON file")
    return p.parse_args()


def _resolve_csv(data_dir: Path, ts_code: str) -> Path | None:
    # Try multiple locations: {root}/{code}.csv, {root}/etf/{code}.csv, ...
    candidates = [
        data_dir / f"{ts_code}.csv",
        data_dir / "etf" / f"{ts_code}.csv",
        data_dir / "fund" / f"{ts_code}.csv",
        data_dir / "stock" / f"{ts_code}.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_params(config_path: Path) -> Tuple[int, int, int]:
    fast, slow, signal = 12, 26, 9
    if not config_path.exists():
        return fast, slow, signal
    with config_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    try:
        params = cfg["macd_cross"]["params"]
        fast = int(params.get("fast_period", fast))
        slow = int(params.get("slow_period", slow))
        signal = int(params.get("signal_period", signal))
    except Exception:
        pass
    return fast, slow, signal


def _fmt_date(idx_value) -> str:
    # Index is DatetimeIndex; make compact
    try:
        return pd.to_datetime(idx_value).strftime("%Y-%m-%d")
    except Exception:
        return str(idx_value)


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    config_path = Path(args.config)
    fast, slow, signal = _load_params(config_path)

    # Accept YYYYMMDD for end_date
    end_date = args.end_date
    if end_date and len(end_date) == 8 and end_date.isdigit():
        end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

    print(f"Using MACD params: fast={fast}, slow={slow}, signal={signal}")
    if end_date:
        print(f"End date cutoff: {end_date}")
    print()

    for ts_code in args.tickers:
        print("=" * 80)
        print(f"{ts_code}  — MACD Check")
        print("=" * 80)

        csv_path = _resolve_csv(data_dir, ts_code)
        if not csv_path:
            print(f"! Data file for {ts_code} not found under {data_dir}")
            continue

        try:
            df = load_chinese_ohlcv_data(csv_path, start_date=None, end_date=end_date, verbose=False)
        except Exception as exc:
            print(f"! Failed to load {ts_code}: {exc}")
            continue

        if len(df) < max(fast, slow, signal) + 5:
            print(f"! Not enough data ({len(df)} rows). Skipping.")
            continue

        macd_line, signal_line, hist = MACD(df["Close"], fast, slow, signal)

        # Build a compact frame for tail print
        tail_n = max(2, args.rows)
        tail = df.tail(tail_n).copy()
        tail["MACD"] = pd.Series(macd_line, index=df.index).tail(tail_n)
        tail["Signal"] = pd.Series(signal_line, index=df.index).tail(tail_n)
        tail["Hist"] = pd.Series(hist, index=df.index).tail(tail_n)

        # Print rows
        print(f"{'Date':<12} {'Close':>8}  {'MACD':>10}  {'Signal':>10}  {'Hist':>10}")
        for idx, row in tail.iterrows():
            print(
                f"{_fmt_date(idx):<12} "
                f"{row['Close']:>8.3f}  "
                f"{row['MACD']:>10.6f}  "
                f"{row['Signal']:>10.6f}  "
                f"{row['Hist']:>10.6f}"
            )

        # Cross check on the last bar
        macd_prev, macd_now = macd_line[-2], macd_line[-1]
        sig_prev, sig_now = signal_line[-2], signal_line[-1]
        last_date = _fmt_date(df.index[-1])
        print()
        if macd_prev <= sig_prev and macd_now > sig_now:
            print(f"[{last_date}] Cross: BUY (MACD crossed ABOVE Signal)")
        elif macd_prev >= sig_prev and macd_now < sig_now:
            print(f"[{last_date}] Cross: SELL (MACD crossed BELOW Signal)")
        else:
            side = "ABOVE" if macd_now > sig_now else "BELOW"
            print(f"[{last_date}] No cross. MACD is {side} Signal.")
        print()


if __name__ == "__main__":
    main()
