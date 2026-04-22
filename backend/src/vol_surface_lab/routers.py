from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from vol_surface_lab.csv_io import parse_options_csv
from vol_surface_lab.models import (
    DatasetUploadResponse,
    SurfaceComputeRequest,
    SurfaceComputeResponse,
)
from vol_surface_lab.store import store
from vol_surface_lab.surface import compute_surface, validate_rows

router = APIRouter()


@router.post(
    "/api/v1/datasets",
    response_model=DatasetUploadResponse,
    summary="Upload EOD options CSV",
    description=(
        "Required columns: underlying, expiry, strike, iv. "
        "Optional: open_interest, volume. IV is decimal (e.g. 0.25). "
        "UTF-8 with optional BOM."
    ),
)
async def upload_dataset(
    file: Annotated[UploadFile, File(description="CSV file with canonical columns")],
) -> DatasetUploadResponse:
    from vol_surface_lab.config import get_settings

    settings = get_settings()
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(413, "File too large")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise HTTPException(400, "CSV must be UTF-8") from e

    try:
        df, parse_drops = parse_options_csv(text)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    df_valid, _, validate_drops = validate_rows(df)
    ingest_drops = {**parse_drops, **validate_drops}

    did = store.add_dataset(df_valid, ingest_drops)
    underlyings = sorted(df_valid["underlying"].unique().tolist())
    n_exp = int(df_valid["expiry"].nunique())
    return DatasetUploadResponse(
        dataset_id=did,
        rows=len(df_valid),
        underlyings=underlyings,
        expiries=n_exp,
        rows_dropped=ingest_drops,
    )


@router.post(
    "/api/v1/surfaces",
    response_model=SurfaceComputeResponse,
    summary="Compute IV surface grid",
    description=(
        "PCHIP on total variance w=σ²T vs log-moneyness k=log(K/F) per expiry; "
        "linear interpolation of w between expiries in time. "
        "F is the supplied spot (v1 forward proxy). Null IV outside strike hull per slice."
    ),
)
def compute_surface_endpoint(body: SurfaceComputeRequest) -> SurfaceComputeResponse:
    stored = store.get_dataset(body.dataset_id)
    if stored is None:
        raise HTTPException(404, "dataset_id not found")

    df = stored.df
    if df["underlying"].nunique() != 1:
        raise HTTPException(
            400,
            "v1 supports a single underlying per dataset; split CSV by ticker",
        )

    try:
        resp, pq_bytes = compute_surface(
            df,
            body,
            rows_used=len(df),
            rows_dropped=dict(stored.ingest_drops),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    store.add_surface(resp, pq_bytes)
    return resp


@router.get(
    "/api/v1/surfaces/{surface_id}/grid.parquet",
    summary="Download surface grid as Parquet",
    response_class=Response,
)
def download_grid_parquet(surface_id: str) -> Response:
    s = store.get_surface(surface_id)
    if s is None:
        raise HTTPException(404, "surface_id not found")
    return Response(
        content=s.parquet,
        media_type="application/vnd.apache.parquet",
        headers={"Content-Disposition": f'attachment; filename="surface_{surface_id}.parquet"'},
    )


@router.get(
    "/api/v1/surfaces/{surface_id}/grid.json",
    response_model=SurfaceComputeResponse,
    summary="Fetch surface grid as JSON (same shape as compute response)",
)
def get_grid_json(surface_id: str) -> SurfaceComputeResponse:
    s = store.get_surface(surface_id)
    if s is None:
        raise HTTPException(404, "surface_id not found")
    return s.response
