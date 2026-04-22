from __future__ import annotations

import io

import pandas as pd

REQUIRED_COLUMNS = {"underlying", "expiry", "strike", "iv"}
OPTIONAL_COLUMNS = {"open_interest", "volume"}
ALL_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


def parse_options_csv(content: str) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Parse and validate canonical CSV. Returns dataframe and drop stats (empty here;
    invalid rows raise ValueError).
    """
    buf = io.StringIO(content)
    df = pd.read_csv(buf)
    cols = {c.strip().lower() for c in df.columns}
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}. Found: {sorted(df.columns)}"
        )

    df.columns = [c.strip().lower() for c in df.columns]
    extra = set(df.columns) - ALL_COLUMNS
    if extra:
        raise ValueError(f"Unknown columns: {sorted(extra)}. Allowed: {sorted(ALL_COLUMNS)}")

    for c in REQUIRED_COLUMNS:
        if c not in df.columns:
            raise ValueError(f"Missing column after normalize: {c}")

    df["underlying"] = df["underlying"].astype(str).str.strip().str.upper()
    df["expiry"] = pd.to_datetime(df["expiry"], utc=False).dt.date
    df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
    df["iv"] = pd.to_numeric(df["iv"], errors="coerce")

    if "open_interest" in df.columns:
        df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce").astype("Int64")
    else:
        df["open_interest"] = pd.NA

    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume"] = pd.NA

    bad = df["strike"].isna() | df["iv"].isna() | df["underlying"].isna() | df["expiry"].isna()
    dropped_invalid = int(bad.sum())
    df = df.loc[~bad].copy()
    if df.empty:
        raise ValueError("No valid rows after coercion")

    return df, {"invalid_coercion": dropped_invalid}
