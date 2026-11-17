import pandas as pd


def test_pandas_date_range_works():
    dates = pd.date_range("2026-01-01", periods=3, freq="D")

    assert len(dates) == 3
    assert str(dates[0].date()) == "2026-01-01"
    assert str(dates[-1].date()) == "2026-01-03"


def test_pandas_is_available():
    assert pd.__version__