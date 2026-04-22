from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

IV_MIN = 1e-6
IV_MAX = 5.0

SURFACE_METHOD_VERSION = "pchip_var_lin_time_v1"


class OptionQuoteRow(BaseModel):
    """One row from the canonical EOD CSV."""

    underlying: str = Field(min_length=1, max_length=32)
    expiry: date
    strike: float = Field(gt=0)
    iv: float = Field(gt=0)
    open_interest: int | None = None
    volume: float | None = None

    @field_validator("iv")
    @classmethod
    def iv_in_range(cls, v: float) -> float:
        if not (IV_MIN <= v <= IV_MAX):
            raise ValueError(f"iv must be in [{IV_MIN}, {IV_MAX}], got {v}")
        return v

    @field_validator("underlying")
    @classmethod
    def strip_underlying(cls, v: str) -> str:
        return v.strip().upper()


class SurfaceComputeRequest(BaseModel):
    dataset_id: str = Field(description="UUID returned from POST /api/v1/datasets")
    as_of_date: date = Field(description="Valuation date for year fraction to each expiry")
    spot: float = Field(gt=0, description="Forward proxy in v1: spot F used as F in log-moneyness")
    n_k: int = Field(default=32, ge=4, le=256)
    n_t: int = Field(default=24, ge=2, le=128)
    k_min: float | None = Field(
        default=None,
        description="Optional min log-moneyness; default from data with margin",
    )
    k_max: float | None = Field(default=None, description="Optional max log-moneyness")
    t_min: float | None = Field(
        default=None,
        description="Optional min year fraction (ACT/365F); default from data",
    )
    t_max: float | None = Field(default=None, description="Optional max year fraction")


class ChartGrid(BaseModel):
    """Chart-oriented IV grid (rows index T, columns index k)."""

    k: list[float]
    t: list[float]
    iv: list[list[float | None]]


class SurfaceAssumptions(BaseModel):
    surface_method_version: str
    as_of_date: date
    spot: float
    year_fraction_basis: str = "ACT/365F"
    forward_proxy: str = "F equals user supplied spot (same for all expiries in v1)"
    extrapolation: str = (
        "Outside strike hull of each expiry slice: null IV (PCHIP extrapolate=False)"
    )
    time_interpolation: str = (
        "Linear in total variance w between bracketing expiries; outside T hull: null"
    )
    n_k: int
    n_t: int
    k_range: tuple[float, float]
    t_range: tuple[float, float]
    rows_in_dataset: int
    rows_used: int
    rows_dropped: dict[str, int] = Field(default_factory=dict)


class SurfaceComputeResponse(BaseModel):
    surface_id: str
    chart: ChartGrid
    assumptions: SurfaceAssumptions


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    rows: int
    underlyings: list[str]
    expiries: int
    rows_dropped: dict[str, int] = Field(
        default_factory=dict,
        description="Rows removed at ingest (coercion failures, schema validation, etc.)",
    )
