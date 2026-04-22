from __future__ import annotations

from io import BytesIO

import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from vol_surface_lab.main import create_app


def test_health() -> None:
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_upload_and_surface_roundtrip() -> None:
    app = create_app()
    client = TestClient(app)
    csv = (
        "underlying,expiry,strike,iv\n"
        "ZZ,2026-09-18,90,0.22\n"
        "ZZ,2026-09-18,100,0.20\n"
        "ZZ,2026-09-18,110,0.24\n"
        "ZZ,2026-12-18,90,0.24\n"
        "ZZ,2026-12-18,100,0.21\n"
        "ZZ,2026-12-18,110,0.26\n"
    )
    up = client.post(
        "/api/v1/datasets",
        files={"file": ("q.csv", BytesIO(csv.encode()), "text/csv")},
    )
    assert up.status_code == 200, up.text
    payload = up.json()
    did = payload["dataset_id"]
    assert "rows_dropped" in payload
    assert isinstance(payload["rows_dropped"], dict)

    body = {
        "dataset_id": did,
        "as_of_date": "2026-01-02",
        "spot": 100.0,
        "n_k": 16,
        "n_t": 8,
    }
    surf = client.post("/api/v1/surfaces", json=body)
    assert surf.status_code == 200, surf.text
    sid = surf.json()["surface_id"]

    pq_r = client.get(f"/api/v1/surfaces/{sid}/grid.parquet")
    assert pq_r.status_code == 200
    table = pq.read_table(BytesIO(pq_r.content))
    assert table.num_rows > 0

    js = client.get(f"/api/v1/surfaces/{sid}/grid.json")
    assert js.status_code == 200
    assert js.json()["surface_id"] == sid
