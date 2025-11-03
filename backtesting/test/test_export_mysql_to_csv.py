import importlib.util
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "export_mysql_to_csv.py"
)
SPEC = importlib.util.spec_from_file_location("export_mysql_to_csv", MODULE_PATH)
EXPORT_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader  # 确保模块加载器存在
SPEC.loader.exec_module(EXPORT_MODULE)  # type: ignore[union-attr]
MySQLToCSVExporter = EXPORT_MODULE.MySQLToCSVExporter


def test_enrich_daily_output_adds_name_and_adjustments_for_etf(tmp_path):
    exporter = MySQLToCSVExporter(output_dir=str(tmp_path))
    exporter._instrument_name_cache["etf"] = {"159001.SZ": "测试ETF"}

    frame = pd.DataFrame(
        {
            "trade_date": ["20240101", "20240102", "20240103"],
            "open": [10.0, 10.5, 10.3],
            "high": [10.2, 10.6, 10.4],
            "low": [9.9, 10.4, 10.1],
            "close": [10.0, 10.5, 10.2],
            "pre_close": [10.0, 10.0, 10.5],
            "change": [0.0, 0.5, -0.3],
            "pct_chg": [0.0, 5.0, -2.8571],
            "volume": [1000, 1100, 1200],
            "amount": [10000.0, 11000.0, 10500.0],
        }
    )

    enriched = exporter._enrich_daily_output("etf", "159001.SZ", frame)

    assert list(enriched.columns) == exporter.DAILY_COLUMN_LAYOUT["etf"]
    assert enriched["instrument_name"].tolist() == ["测试ETF"] * len(frame)

    adj_factor = enriched["adj_factor"].tolist()
    adj_close = enriched["adj_close"].tolist()
    assert adj_factor == pytest.approx([0.9803917243, 1.0294113106, 1.0])
    assert adj_close == pytest.approx(
        [9.8039172434, 10.8088187608, frame["close"].iloc[-1]]
    )


def test_enrich_daily_output_computes_fund_adjustments(tmp_path):
    exporter = MySQLToCSVExporter(output_dir=str(tmp_path))
    exporter._instrument_name_cache["fund"] = {"000037.OF": "测试基金"}

    frame = pd.DataFrame(
        {
            "trade_date": ["20240101", "20240102"],
            "unit_nav": [1.0, 1.1],
            "accum_nav": [1.0, 1.1],
            "adj_nav": [1000.0, 1100.0],
            "accum_div": [0.0, 0.0],
            "net_asset": [100.0, 120.0],
            "total_netasset": [100.0, 120.0],
        }
    )

    enriched = exporter._enrich_daily_output("fund", "000037.OF", frame)

    assert list(enriched.columns) == exporter.DAILY_COLUMN_LAYOUT["fund"]
    assert enriched["instrument_name"].tolist() == ["测试基金"] * len(frame)
    assert enriched["adj_close"].tolist() == pytest.approx(frame["adj_nav"].tolist())

    expected_factor = [1000.0, 1000.0]
    assert enriched["adj_factor"].dropna().tolist() == pytest.approx(expected_factor)
