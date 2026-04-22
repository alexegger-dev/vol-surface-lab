from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.interpolate import PchipInterpolator

from vol_surface_lab.models import (
    SURFACE_METHOD_VERSION,
    ChartGrid,
    OptionQuoteRow,
    SurfaceAssumptions,
    SurfaceComputeRequest,
    SurfaceComputeResponse,
)


def year_fraction_act365f(as_of: date, expiry: date) -> float:
    return (expiry - as_of).days / 365.0


def _aggregate_duplicate_k(k: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Average w for duplicate k (numerical duplicates after log)."""
    order = np.argsort(k)
    k = k[order]
    w = w[order]
    if len(k) == 0:
        return k, w
    out_k: list[float] = []
    out_w: list[float] = []
    i = 0
    while i < len(k):
        j = i
        while j + 1 < len(k) and k[j + 1] == k[i]:
            j += 1
        out_k.append(float(k[i]))
        out_w.append(float(np.mean(w[i : j + 1])))
        i = j + 1
    return np.asarray(out_k), np.asarray(out_w)


def build_pchip_w_of_k(
    strikes: np.ndarray,
    ivs: np.ndarray,
    T: float,
    F: float,
) -> PchipInterpolator | None:
    if T <= 0:
        return None
    w = (ivs**2) * T
    k = np.log(strikes / F)
    k, w = _aggregate_duplicate_k(k, w)
    if len(k) < 2:
        return None
    return PchipInterpolator(k, w, extrapolate=False)


def eval_slice(interp: PchipInterpolator | None, k_grid: np.ndarray) -> np.ndarray:
    if interp is None:
        return np.full_like(k_grid, np.nan, dtype=float)
    return np.asarray(interp(k_grid), dtype=float)


def compute_surface(
    df: pd.DataFrame,
    req: SurfaceComputeRequest,
    rows_used: int,
    rows_dropped: dict[str, int],
) -> tuple[SurfaceComputeResponse, bytes]:
    """
    Build IV grid on (k, T) using PCHIP in w per expiry and linear w between expiries.
    """
    as_of = req.as_of_date
    F = float(req.spot)

    work = df.copy()
    work["T"] = work["expiry"].map(lambda e: year_fraction_act365f(as_of, e))
    work = work.loc[work["T"] > 0]
    if work.empty:
        raise ValueError("All expiries on or before as_of_date")

    unique_T = np.sort(work["T"].unique())
    if len(unique_T) == 0:
        raise ValueError("No expiries")

    # Per-expiry PCHIP in (k, w)
    expiry_times: list[float] = []
    interps: list[PchipInterpolator | None] = []
    for T in unique_T:
        Tf = float(T)
        sub = work.loc[np.isclose(work["T"].to_numpy(dtype=float), Tf, rtol=0.0, atol=1e-12)]
        strikes = sub["strike"].to_numpy(dtype=float)
        ivs = sub["iv"].to_numpy(dtype=float)
        p = build_pchip_w_of_k(strikes, ivs, float(T), F)
        expiry_times.append(float(T))
        interps.append(p)

    expiry_times_arr = np.asarray(expiry_times, dtype=float)

    # k range from data with margin
    ks_data: list[float] = []
    for T in unique_T:
        Tf = float(T)
        sub = work.loc[np.isclose(work["T"].to_numpy(dtype=float), Tf, rtol=0.0, atol=1e-12)]
        strikes = sub["strike"].to_numpy(dtype=float)
        ks_data.extend(np.log(strikes / F).tolist())
    ks_arr = np.asarray(ks_data, dtype=float)
    pad = 0.02 * (ks_arr.max() - ks_arr.min() + 1e-12)
    k_lo = float(ks_arr.min() - pad) if req.k_min is None else float(req.k_min)
    k_hi = float(ks_arr.max() + pad) if req.k_max is None else float(req.k_max)
    if k_hi <= k_lo:
        raise ValueError("Invalid k range")

    t_lo = float(expiry_times_arr.min()) if req.t_min is None else float(req.t_min)
    t_hi = float(expiry_times_arr.max()) if req.t_max is None else float(req.t_max)

    if len(unique_T) == 1:
        t_points = np.array([float(unique_T[0])], dtype=float)
        n_t_eff = 1
    else:
        t_points = np.linspace(t_lo, t_hi, req.n_t)
        n_t_eff = req.n_t

    k_points = np.linspace(k_lo, k_hi, req.n_k)

    iv_grid = np.full((len(t_points), len(k_points)), np.nan, dtype=float)

    for ti, t in enumerate(t_points):
        if t < expiry_times_arr.min() - 1e-15 or t > expiry_times_arr.max() + 1e-15:
            continue
        # find bracket in expiry_times_arr
        idx = np.searchsorted(expiry_times_arr, t, side="right")
        if idx <= 0 or idx > len(expiry_times_arr):
            continue
        t0 = expiry_times_arr[idx - 1]
        t1 = expiry_times_arr[idx] if idx < len(expiry_times_arr) else expiry_times_arr[idx - 1]

        if np.isclose(t, t0):
            w_row = eval_slice(interps[idx - 1], k_points)
            iv_row = np.sqrt(np.maximum(w_row, 0.0) / t)
            iv_row[~np.isfinite(w_row)] = np.nan
            iv_grid[ti, :] = iv_row
            continue

        if idx >= len(expiry_times_arr):
            continue

        if np.isclose(t0, t1):
            w_row = eval_slice(interps[idx - 1], k_points)
        else:
            w_a = eval_slice(interps[idx - 1], k_points)
            w_b = eval_slice(interps[idx], k_points)
            alpha = (t - t0) / (t1 - t0)
            w_row = w_a + alpha * (w_b - w_a)
        bad = np.isnan(w_row) | (w_row < 0)
        iv_row = np.sqrt(np.maximum(w_row, 0.0) / t)
        iv_row[bad] = np.nan
        iv_grid[ti, :] = iv_row

    iv_list: list[list[float | None]] = []
    for i in range(iv_grid.shape[0]):
        row: list[float | None] = []
        for j in range(iv_grid.shape[1]):
            v = iv_grid[i, j]
            row.append(None if (v is None or not np.isfinite(v)) else float(v))
        iv_list.append(row)

    chart = ChartGrid(
        k=[float(x) for x in k_points],
        t=[float(x) for x in t_points],
        iv=iv_list,
    )

    assumptions = SurfaceAssumptions(
        surface_method_version=SURFACE_METHOD_VERSION,
        as_of_date=as_of,
        spot=F,
        n_k=req.n_k,
        n_t=n_t_eff,
        k_range=(k_lo, k_hi),
        t_range=(float(t_points.min()), float(t_points.max())),
        rows_in_dataset=len(df),
        rows_used=rows_used,
        rows_dropped=dict(rows_dropped),
    )

    # Parquet: long grid + metadata columns
    records: list[dict[str, object]] = []
    for ti, tt in enumerate(t_points):
        for kj, kk in enumerate(k_points):
            ivv = iv_list[ti][kj]
            records.append(
                {
                    "log_moneyness": kk,
                    "year_fraction": float(tt),
                    "iv": ivv if ivv is not None else float("nan"),
                    "surface_method_version": SURFACE_METHOD_VERSION,
                    "as_of_date": str(as_of),
                    "spot": F,
                }
            )
    table = pa.Table.from_pylist(records)
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink)
    parquet_bytes = sink.getvalue().to_pybytes()

    resp = SurfaceComputeResponse(
        surface_id="",  # filled by caller
        chart=chart,
        assumptions=assumptions,
    )
    return resp, parquet_bytes


def validate_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int, dict[str, int]]:
    """Apply OptionQuoteRow rules; drop invalid IV/strike rows."""
    dropped: dict[str, int] = {"iv_out_of_range": 0, "validation_error": 0}
    keep_mask = []
    for _, r in df.iterrows():
        try:
            exp = r["expiry"]
            if isinstance(exp, pd.Timestamp):
                exp = exp.date()
            OptionQuoteRow(
                underlying=str(r["underlying"]),
                expiry=exp,
                strike=float(r["strike"]),
                iv=float(r["iv"]),
                open_interest=int(r["open_interest"]) if pd.notna(r.get("open_interest")) else None,
                volume=float(r["volume"]) if pd.notna(r.get("volume")) else None,
            )
            keep_mask.append(True)
        except Exception:
            keep_mask.append(False)
            dropped["validation_error"] += 1
    out = df.loc[keep_mask].copy()
    if out.empty:
        raise ValueError("No rows passed validation")
    return out, int(len(out)), dropped
