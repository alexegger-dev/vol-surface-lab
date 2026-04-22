# Vol Surface Lab — API

FastAPI service under `src/vol_surface_lab/`: CSV upload, schema validation, deterministic implied-volatility surface (`pchip_var_lin_time_v1`), JSON for charts, Parquet export.

## Commands

```bash
uv sync --group dev
uv run ruff check src tests
uv run pytest
uv run uvicorn vol_surface_lab.main:app --reload --host 0.0.0.0 --port 8000
```

Environment variables are documented in the repo root [`.env.example`](../.env.example). Architecture and CSV contract are in the root [README.md](../README.md).
