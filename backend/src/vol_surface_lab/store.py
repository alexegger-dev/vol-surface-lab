from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pandas as pd

from vol_surface_lab.models import SurfaceComputeResponse


@dataclass
class StoredSurface:
    response: SurfaceComputeResponse
    parquet: bytes


@dataclass
class StoredDataset:
    """Validated quotes plus ingest-time drop counts (surfaced again on compute)."""

    df: pd.DataFrame
    ingest_drops: dict[str, int]


@dataclass
class DatasetStore:
    datasets: dict[str, StoredDataset] = field(default_factory=dict)
    surfaces: dict[str, StoredSurface] = field(default_factory=dict)

    def add_dataset(self, df: pd.DataFrame, ingest_drops: dict[str, int]) -> str:
        did = str(uuid.uuid4())
        self.datasets[did] = StoredDataset(df=df, ingest_drops=dict(ingest_drops))
        return did

    def get_dataset(self, dataset_id: str) -> StoredDataset | None:
        return self.datasets.get(dataset_id)

    def add_surface(self, resp: SurfaceComputeResponse, parquet: bytes) -> str:
        sid = str(uuid.uuid4())
        resp.surface_id = sid
        self.surfaces[sid] = StoredSurface(response=resp, parquet=parquet)
        return sid

    def get_surface(self, surface_id: str) -> StoredSurface | None:
        return self.surfaces.get(surface_id)


store = DatasetStore()
