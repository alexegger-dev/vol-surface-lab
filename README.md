# Vol Surface Lab

[![CI](https://github.com/alexegger224/vol-surface-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/alexegger224/vol-surface-lab/actions/workflows/ci.yml)

Full-stack **research** tool for implied volatility: upload end-of-day option quotes (CSV), validate the schema, run a **versioned, deterministic** smoother in total variance, then inspect the surface in the browser (heatmap and 3D) and export the grid as **Apache Parquet** or JSON.

**Not in scope for v1:** broker APIs, live market data, execution, portfolios, or suitability advice.

## Interview signal

| Lens                  | What this repo proves                                                                                                                              |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Quant + API craft** | Versioned **deterministic** IV surface (`pchip_var_lin_time_v1`), explicit ACT/365F and moneyness assumptions—readable numerics, not black-box ML. |
| **Full stack**        | FastAPI + Pydantic/OpenAPI, pandas/SciPy pipeline, Next.js 15 + Plotly visualization, Parquet export.                                              |
| **Production habits** | `uv.lock`, Ruff, pytest with synthetic ground-truth surfaces, Docker Compose, **GitHub Actions** (badge above).                                    |
| **Communication**     | Research disclaimer, methodology section, and documented **drop counts** so stakeholders know what changed in the grid.                            |

---

## Why this repo exists

Demonstrates a small production-shaped slice of work hiring teams care about: typed APIs (Pydantic + OpenAPI), numeric pipelines (pandas / SciPy), reproducible dependencies (`uv.lock`), automated quality gates (Ruff, pytest, Next build + TypeScript), containerized local dev, and clear documentation of **model assumptions** instead of black-box “ML magic.”

## Stack

| Layer   | Choices                                                                      |
| ------- | ---------------------------------------------------------------------------- |
| API     | Python 3.12+, FastAPI, pandas, SciPy (`PchipInterpolator`), PyArrow          |
| UI      | Next.js 15 (App Router), TypeScript, Plotly (`react-plotly.js`, client-only) |
| Tooling | uv, Ruff, pytest; npm; Docker Compose                                        |
| CI      | GitHub Actions (see note below)                                              |

## Features (v1)

- **CSV ingest** with column checks, UTF-8 (optional BOM), configurable max upload size (`MAX_UPLOAD_BYTES`).
- **Quotes model:** `underlying`, `expiry`, `strike`, `iv`, optional `open_interest`, `volume`.
- **Surface engine** `pchip_var_lin_time_v1`: PCHIP on \(w=\sigma^2 T\) vs \(k=\log(K/F)\) per expiry; linear blend of \(w\) in time between expiries; **null** IV outside strike or expiry hulls (no silent extrapolation).
- **API:** multipart upload, JSON compute response with `chart` + `assumptions` (method version, grid bounds, **ingest row drop counts**), Parquet + JSON grid downloads.
- **UI:** upload, parameters, Plotly heatmap + 3D surface, Parquet download, persistent **research disclaimer** in the footer.

## Methodology (v1)

Version string: `pchip_var_lin_time_v1` (returned in API JSON and Parquet columns).

- **Year fraction:** ACT/365F from `as_of_date` to each `expiry`.
- **Log-moneyness:** \(k = \log(K/F)\). **\(F\)** is the user-supplied **spot** (same for all rows in v1)—documented as a forward _proxy_, not an implied forward curve.
- **Per expiry:** `scipy.interpolate.PchipInterpolator` on \((k, w)\) with `extrapolate=False`.
- **Across expiries:** linear interpolation of \(w\) in \(T\) between bracketing expiries at fixed \(k\).
- **Single expiry:** time grid collapses to that expiry’s \(T\); `n_t` is effectively ignored.

Design goal: **reproducibility and explicit assumptions** over opaque curve fitting.

## Repository layout

```
vol-surface-lab/
├── backend/           # FastAPI app (src layout: vol_surface_lab)
├── frontend/          # Next.js UI
├── docker-compose.yml
├── .env.example
└── .github/workflows/ # CI (see note)
```

## CSV schema

**Required:** `underlying`, `expiry`, `strike`, `iv`  
**Optional:** `open_interest`, `volume`

- `iv` is a **decimal** (e.g. `0.25` for 25% vol).
- Dates: `YYYY-MM-DD` recommended.

Example:

```csv
underlying,expiry,strike,iv,open_interest,volume
DEMO,2026-09-18,95,0.28,,
DEMO,2026-09-18,100,0.25,1200,500
DEMO,2026-09-18,105,0.27,,
```

## Quick start

### Backend

```bash
cd backend
uv sync --group dev
uv run uvicorn vol_surface_lab.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for OpenAPI.

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Docker Compose

From the repo root:

```bash
docker compose up --build
```

The browser talks to whatever URL was baked into the web image as `NEXT_PUBLIC_API_URL` at **build** time (see `docker-compose.yml`). Change the build arg if the API is not on the host loopback.

## HTTP API

| Method | Path                                 | Purpose                                                                                     |
| ------ | ------------------------------------ | ------------------------------------------------------------------------------------------- |
| `POST` | `/api/v1/datasets`                   | Multipart CSV → `dataset_id`, row counts, `rows_dropped`                                    |
| `POST` | `/api/v1/surfaces`                   | JSON `{ dataset_id, as_of_date, spot, n_k, n_t, … }` → `surface_id`, `chart`, `assumptions` |
| `GET`  | `/api/v1/surfaces/{id}/grid.parquet` | Download grid                                                                               |
| `GET`  | `/api/v1/surfaces/{id}/grid.json`    | Same payload as compute                                                                     |
| `GET`  | `/health`                            | Liveness                                                                                    |

**v1 constraint:** one underlying per dataset at compute time (split multi-ticker CSVs before upload).

**Persistence:** datasets and surfaces live **in process memory**; restarting the API clears them.

## Tests

Synthetic tests build a known linear \(w(k)\) surface, run it through the pipeline, and assert interior IV matches within tolerance; the API test covers upload → compute → Parquet round-trip.

```bash
cd backend
uv run pytest
```

## Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs backend (Ruff + pytest with frozen lockfile) and frontend (`npm ci`, production build, `tsc --noEmit`).

> **CI layout:** GitHub Actions only runs workflows from the **repository root**. If this code currently lives inside a larger mono-repo, either publish **`vol-surface-lab` as its own Git repository** (recommended) or add a root-level workflow with `paths:` / `working-directory` pointing at this subtree.

## Configuration

See [`.env.example`](.env.example) for `CORS_ORIGINS`, `MAX_UPLOAD_BYTES`, and `NEXT_PUBLIC_API_URL`.

## Disclaimer

Vol Surface Lab is for **education and quantitative research** only. Outputs are **not** investment advice, not a recommendation to trade, and can be materially wrong. Volatility modeling depends on inputs, discounting, dividends and borrow, liquidity, and data quality. There is **no** suitability or compliance review.
