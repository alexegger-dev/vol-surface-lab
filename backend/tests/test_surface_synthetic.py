from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from vol_surface_lab.models import SurfaceComputeRequest
from vol_surface_lab.surface import compute_surface, year_fraction_act365f


def _linear_w(k: np.ndarray) -> np.ndarray:
    return 0.04 + 0.02 * k


def _build_synthetic_frame(
    *,
    F: float,
    as_of: date,
    expiries: list[date],
    k_samples: np.ndarray,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    underlying = "SYN"
    for exp in expiries:
        T = year_fraction_act365f(as_of, exp)
        assert T > 0
        for k in k_samples:
            K = float(F * np.exp(k))
            w = float(_linear_w(np.array([k]))[0])
            iv = float(np.sqrt(max(w, 1e-12) / T))
            rows.append(
                {
                    "underlying": underlying,
                    "expiry": exp,
                    "strike": K,
                    "iv": iv,
                    "open_interest": None,
                    "volume": None,
                }
            )
    return pd.DataFrame(rows)


def test_single_expiry_recovers_linear_variance_surface() -> None:
    F = 100.0
    as_of = date(2026, 1, 2)
    exp = date(2026, 7, 1)
    ks = np.linspace(-0.25, 0.25, num=25)
    df = _build_synthetic_frame(F=F, as_of=as_of, expiries=[exp], k_samples=ks)
    T = year_fraction_act365f(as_of, exp)

    req = SurfaceComputeRequest(
        dataset_id="ignored",
        as_of_date=as_of,
        spot=F,
        n_k=48,
        n_t=8,
        k_min=-0.2,
        k_max=0.2,
        t_min=None,
        t_max=None,
    )
    resp, _pq_bytes = compute_surface(df, req, rows_used=len(df), rows_dropped={})

    assert resp.assumptions.surface_method_version
    k_grid = np.asarray(resp.chart.k, dtype=float)
    t_grid = np.asarray(resp.chart.t, dtype=float)
    assert t_grid.shape == (1,)
    assert np.isclose(t_grid[0], T)

    w_expect = _linear_w(k_grid)
    iv_expect = np.sqrt(np.maximum(w_expect, 0.0) / T)

    iv_hat = np.asarray(
        [row for row in resp.chart.iv[0]],
        dtype=float,
    )
    mask = np.isfinite(iv_hat) & np.isfinite(iv_expect)
    assert mask.sum() > 10
    max_err = float(np.max(np.abs(iv_hat[mask] - iv_expect[mask])))
    assert max_err < 1e-3


def test_two_expiries_time_interpolation_matches_linear_blend() -> None:
    F = 100.0
    as_of = date(2026, 1, 2)
    e1 = date(2026, 4, 1)
    e2 = date(2026, 10, 1)
    ks = np.linspace(-0.15, 0.15, num=21)
    df = _build_synthetic_frame(F=F, as_of=as_of, expiries=[e1, e2], k_samples=ks)
    T1 = year_fraction_act365f(as_of, e1)
    T2 = year_fraction_act365f(as_of, e2)
    t_mid = float(0.5 * (T1 + T2))

    req = SurfaceComputeRequest(
        dataset_id="ignored",
        as_of_date=as_of,
        spot=F,
        n_k=32,
        n_t=64,
        k_min=-0.12,
        k_max=0.12,
        t_min=t_mid,
        t_max=t_mid,
    )
    resp, pq_bytes = compute_surface(df, req, rows_used=len(df), rows_dropped={})

    k_grid = np.asarray(resp.chart.k, dtype=float)
    alpha = (t_mid - T1) / (T2 - T1)
    w1 = _linear_w(k_grid)
    w2 = _linear_w(k_grid)
    w_mid = w1 + alpha * (w2 - w1)
    iv_expect = np.sqrt(np.maximum(w_mid, 0.0) / t_mid)

    row = resp.chart.iv[0]
    iv_hat = np.asarray(row, dtype=float)
    mask = np.isfinite(iv_hat)
    max_err = float(np.max(np.abs(iv_hat[mask] - iv_expect[mask])))
    assert max_err < 1e-3

    from io import BytesIO

    table = pq.read_table(BytesIO(pq_bytes))
    assert set(table.column_names) >= {
        "log_moneyness",
        "year_fraction",
        "iv",
        "surface_method_version",
        "as_of_date",
        "spot",
    }
