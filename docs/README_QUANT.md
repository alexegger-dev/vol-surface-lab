# Quant lens (methodology and alternatives)

This addendum is for **quant hiring loops** and readers who want SVI-class context—not required for AI infra roles.

## Why PCHIP in total variance, not SVI?

**SVI (Gatheral)** and related parameterizations are the industry standard for **arbitrage-aware** equity index surfaces when you need a production pricing engine.

This workbench uses **PCHIP** on total variance \(w = \sigma^2 T\) vs log-moneyness \(k\) because:

- **Deterministic and auditable**—no optimizer convergence stories in the hot path.
- **Monotonicity-preserving** interpolation reduces certain pathological wiggles compared to naive splines.
- **Small surface area** in code—appropriate for a portfolio demo, not a full vol desk stack.

**For production pricing:** SVI/SVI-JW or another arb-aware parameterization is usually the right call. Treat this repo as a **research UI + API discipline** demo, not a broker-quality pricer.

## Sample output

After running a compute, inspect API JSON for:

- `method_version` / assumptions block
- **Drop counts** from ingest validation (transparency for stakeholders)
- Grid downloads (**Parquet** / JSON) for offline checks

## Benchmarking interpolation (optional)

If you extend this repo, a credible check is synthetic surfaces where ground truth is known analytically—report max absolute error on a dense grid inside the **hull** only (this engine intentionally returns null outside the hull).
