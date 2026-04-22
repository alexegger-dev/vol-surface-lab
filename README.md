# Vol Surface Lab

[![CI](https://github.com/alexegger224/vol-surface-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/alexegger224/vol-surface-lab/actions/workflows/ci.yml)

Turn a messy CSV of end-of-day option quotes into a **versioned implied-volatility surface** you can inspect in the browser and hand off as **Parquet** or JSON. The backend is explicit about conventions (day count, moneyness, what got dropped on ingest) so the output is explainable—not a black box.

**Out of scope for v1:** live feeds, broker APIs, execution, portfolios, or any kind of trading advice.

**Deeper quant notes** (PCHIP vs SVI, production caveats): [`docs/README_QUANT.md`](docs/README_QUANT.md).

---

## Try it

```bash
docker compose up --build
```

Open the frontend URL from the logs, upload a small CSV, hit **compute**, and you get a heatmap plus a 3D view and the assumptions payload the API returns.

---

## If you are skimming this repo

- **Numerics:** Total-variance surface built with SciPy `PchipInterpolator` on \(w = \sigma^2 T\) vs log-moneyness, with a **fixed method id** (`pchip_var_lin_time_v1`) so runs are comparable.
- **API:** FastAPI + Pydantic, OpenAPI at `/docs`, multipart CSV ingest, JSON compute response with chart metadata and **row drop counts**.
- **Frontend:** Next.js 15 (App Router), TypeScript, Plotly for heatmap + 3D; Parquet download from the API.
- **Engineering:** `uv` + lockfile, Ruff, pytest (synthetic surfaces + API round-trip), Docker Compose, GitHub Actions on backend and frontend.

That combination is what I wanted to show: something that looks like a small internal research tool, not a tutorial toy.

---

## Stack

| Layer   | Details                                                                                                                            |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| API     | Python 3.12+, FastAPI, pandas, SciPy, PyArrow                                                                                      |
| UI      | Next.js 15, React 19, TypeScript, Plotly (client-only)                                                                             |
| Tooling | uv, Ruff, pytest; Node 22, npm; Docker Compose                                                                                     |
| CI      | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — Ruff + pytest (frozen deps), `npm ci` + production build + `tsc --noEmit` |

---

## What v1 actually does

- CSV upload with schema checks, UTF-8 (BOM-tolerant), configurable `MAX_UPLOAD_BYTES`.
- Quotes: `underlying`, `expiry`, `strike`, `iv`, optional `open_interest`, `volume`.
- **Surface engine** `pchip_var_lin_time_v1`: PCHIP in \(w\) vs \(k = \log(K/F)\) per expiry; linear blend of \(w\) in time between expiries; **null** IV outside the strike/expiry hull (no silent extrapolation).
- **UI:** Upload flow, parameters, Plotly heatmap and 3D surface, Parquet download, and a **research disclaimer** pinned in the footer.
- **Responses:** JSON with `chart` + `assumptions` (version string, grid bounds, ingest drops); grid as Parquet or JSON.

---

## Methodology (short)

Version string: `pchip_var_lin_time_v1` (surfaced in API JSON and Parquet metadata).

- **Year fraction:** ACT/365F from `as_of_date` to each `expiry`.
- **Log-moneyness:** \(k = \log(K/F)\). **F** is the user-supplied **spot** for the whole dataset in v1—documented as a forward _proxy_, not an implied forward curve.
- **Per expiry:** `PchipInterpolator` on \((k, w)\) with `extrapolate=False`.
- **Across expiries:** linear interpolation of \(w\) in \(T\) between bracketing expiries at fixed \(k\).
- **Single expiry:** time grid collapses to that expiry’s \(T\); `n_t` is effectively ignored.

Design bias: **reproducibility and stated assumptions** over opaque curve fitting.

---

## Repository layout

```
vol-surface-lab/
├── backend/           # FastAPI (package: vol_surface_lab)
├── frontend/          # Next.js app
├── docker-compose.yml
├── .env.example
└── .github/workflows/
```

---

## CSV schema

**Required:** `underlying`, `expiry`, `strike`, `iv`  
**Optional:** `open_interest`, `volume`

- `iv` is a **decimal** (e.g. `0.25` for 25% vol).
- Dates: `YYYY-MM-DD` recommended.

```csv
underlying,expiry,strike,iv,open_interest,volume
DEMO,2026-09-18,95,0.28,,
DEMO,2026-09-18,100,0.25,1200,500
DEMO,2026-09-18,105,0.27,,
```

---

## Local development

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

The browser uses `NEXT_PUBLIC_API_URL` **baked in at image build time** (see `docker-compose.yml`). Adjust the build arg if the API is not on loopback.

---

## HTTP API

| Method | Path                                 | Purpose                                                                                     |
| ------ | ------------------------------------ | ------------------------------------------------------------------------------------------- |
| `POST` | `/api/v1/datasets`                   | Multipart CSV → `dataset_id`, counts, `rows_dropped`                                        |
| `POST` | `/api/v1/surfaces`                   | JSON `{ dataset_id, as_of_date, spot, n_k, n_t, … }` → `surface_id`, `chart`, `assumptions` |
| `GET`  | `/api/v1/surfaces/{id}/grid.parquet` | Download grid                                                                               |
| `GET`  | `/api/v1/surfaces/{id}/grid.json`    | Same payload as compute                                                                     |
| `GET`  | `/health`                            | Liveness                                                                                    |

**v1:** one underlying per dataset at compute time—split multi-ticker CSVs before upload.

**Persistence:** datasets and surfaces are **in-memory**; restarting the API clears them.

---

## Tests

Synthetic tests drive a known linear \(w(k)\) surface through the pipeline and assert interior IV within tolerance; the API test covers upload → compute → Parquet round-trip.

```bash
cd backend
uv run pytest
```

---

## Continuous integration

Workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

**Mono-repo note:** GitHub only runs workflows from the **repository root**. If this tree lives inside a larger repo, either publish **vol-surface-lab** as its own remote or add a root workflow with `paths:` / `working-directory` aimed at this folder.

---

## Configuration

See [`.env.example`](.env.example) for `CORS_ORIGINS`, `MAX_UPLOAD_BYTES`, and `NEXT_PUBLIC_API_URL`.

---

## Disclaimer

Vol Surface Lab is for **education and quantitative research** only. Outputs are **not** investment advice, not a recommendation to trade, and can be materially wrong. Volatility modeling depends on inputs, discounting, dividends and borrow, liquidity, and data quality. There is **no** suitability or compliance review.
