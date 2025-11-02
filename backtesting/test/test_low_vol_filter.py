from pathlib import Path

import pytest

from utils.data_loader import (
    InstrumentInfo,
    LowVolatilityConfig,
    is_low_volatility,
    load_instrument_data,
)


TEST_DATA_ROOT = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "chinese_stocks"
    / "daily"
    / "etf"
)


@pytest.fixture(scope="module")
def low_vol_instrument() -> InstrumentInfo:
    csv_path = TEST_DATA_ROOT / "159001.SZ.csv"
    if not csv_path.exists():
        pytest.skip("低波动测试所需的数据文件缺失: 159001.SZ.csv")
    return InstrumentInfo(code="159001.SZ", path=csv_path, category="etf")


@pytest.fixture(scope="module")
def low_vol_dataframe(low_vol_instrument: InstrumentInfo):
    return load_instrument_data(low_vol_instrument, verbose=False)


def test_159001_identified_by_threshold(low_vol_instrument: InstrumentInfo, low_vol_dataframe):
    config = LowVolatilityConfig(threshold=0.02, lookback=60, blacklist=())
    is_low, volatility, reason = is_low_volatility(low_vol_instrument, low_vol_dataframe, config)

    assert is_low, "159001.SZ 应当因为低波动而被过滤"
    assert volatility is not None
    assert volatility < config.threshold
    assert "低于阈值" in reason


def test_159001_respected_by_blacklist(low_vol_instrument: InstrumentInfo, low_vol_dataframe):
    # 使用远低于实际值的阈值，确保黑名单逻辑生效
    config = LowVolatilityConfig(threshold=0.0001, lookback=60, blacklist=("159001.SZ",))
    is_low, volatility, reason = is_low_volatility(low_vol_instrument, low_vol_dataframe, config)

    assert is_low, "黑名单命中后应强制视为低波动"
    assert reason == "命中低波动黑名单"
    # 波动率在黑名单情况下允许缺失，但如果存在则为 float
    if volatility is not None:
        assert isinstance(volatility, float)
