from __future__ import annotations

import pytest

from vol_surface_lab.csv_io import parse_options_csv


def test_parse_minimal_csv() -> None:
    csv = "underlying,expiry,strike,iv\nTEST,2026-06-19,100,0.2\n"
    df, drops = parse_options_csv(csv)
    assert len(df) == 1
    assert drops["invalid_coercion"] == 0
    assert df.iloc[0]["underlying"] == "TEST"


def test_parse_unknown_column() -> None:
    csv = "underlying,expiry,strike,iv,bad\nX,2026-06-19,1,0.1,1\n"
    with pytest.raises(ValueError, match="Unknown columns"):
        parse_options_csv(csv)


def test_parse_optional_columns() -> None:
    csv = (
        "underlying,expiry,strike,iv,open_interest,volume\n"
        "X,2026-06-19,50,0.15,100,1000\n"
    )
    df, _ = parse_options_csv(csv)
    assert df.iloc[0]["open_interest"] == 100
