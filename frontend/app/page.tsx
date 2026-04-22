"use client";

import { useCallback, useMemo, useState } from "react";

import { SurfaceCharts, type ChartPayload } from "./SurfaceCharts";

type Assumptions = {
  surface_method_version: string;
  as_of_date: string;
  spot: number;
  year_fraction_basis: string;
  forward_proxy: string;
  extrapolation: string;
  time_interpolation: string;
  n_k: number;
  n_t: number;
  k_range: [number, number];
  t_range: [number, number];
  rows_in_dataset: number;
  rows_used: number;
  rows_dropped: Record<string, number>;
};

function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
}

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [surfaceId, setSurfaceId] = useState<string | null>(null);
  const [chart, setChart] = useState<ChartPayload | null>(null);
  const [assumptions, setAssumptions] = useState<Assumptions | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [asOf, setAsOf] = useState("2026-01-02");
  const [spot, setSpot] = useState("100");
  const [nK, setNK] = useState("48");
  const [nT, setNT] = useState("24");

  const canCompute = useMemo(() => Boolean(datasetId && !busy), [datasetId, busy]);

  const onUpload = useCallback(async () => {
    setError(null);
    if (!file) {
      setError("Choose a CSV file first.");
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.set("file", file);
      const res = await fetch(`${apiBase()}/api/v1/datasets`, { method: "POST", body: fd });
      if (!res.ok) {
        throw new Error(await res.text());
      }
      const j = (await res.json()) as { dataset_id: string; rows: number };
      setDatasetId(j.dataset_id);
      setSurfaceId(null);
      setChart(null);
      setAssumptions(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }, [file]);

  const onCompute = useCallback(async () => {
    setError(null);
    if (!datasetId) return;
    setBusy(true);
    try {
      const res = await fetch(`${apiBase()}/api/v1/surfaces`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          dataset_id: datasetId,
          as_of_date: asOf,
          spot: Number(spot),
          n_k: Number(nK),
          n_t: Number(nT),
        }),
      });
      if (!res.ok) {
        throw new Error(await res.text());
      }
      const j = (await res.json()) as {
        surface_id: string;
        chart: ChartPayload;
        assumptions: Assumptions;
      };
      setSurfaceId(j.surface_id);
      setChart(j.chart);
      setAssumptions(j.assumptions);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Compute failed");
    } finally {
      setBusy(false);
    }
  }, [datasetId, asOf, spot, nK, nT]);

  const downloadParquet = useCallback(() => {
    if (!surfaceId) return;
    window.open(`${apiBase()}/api/v1/surfaces/${surfaceId}/grid.parquet`, "_blank");
  }, [surfaceId]);

  return (
    <main>
      <h1 style={{ marginTop: 0 }}>Vol Surface Lab</h1>
      <p style={{ color: "var(--muted)", maxWidth: 900 }}>
        Upload end-of-day option quotes as CSV, then compute a deterministic implied-volatility
        surface (PCHIP on total variance in strike space, linear blend in time between expiries).
        This is a research sandbox: assumptions are explicit, not a substitute for production risk
        systems.
      </p>

      <div className="panel">
        <h2 style={{ marginTop: 0 }}>1) Upload CSV</h2>
        <p style={{ color: "var(--muted)", fontSize: 14 }}>
          Required columns: <code>underlying</code>, <code>expiry</code>, <code>strike</code>,{" "}
          <code>iv</code>. Optional: <code>open_interest</code>, <code>volume</code>. IV is a
          decimal (for example <code>0.25</code>).
        </p>
        <div className="row">
          <label>
            File
            <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <button type="button" disabled={busy} onClick={onUpload}>
            Upload
          </button>
        </div>
        {datasetId ? (
          <p style={{ marginBottom: 0 }}>
            Dataset ID: <code>{datasetId}</code>
          </p>
        ) : null}
      </div>

      <div className="panel">
        <h2 style={{ marginTop: 0 }}>2) Compute surface</h2>
        <div className="row">
          <label>
            As-of date
            <input value={asOf} onChange={(e) => setAsOf(e.target.value)} />
          </label>
          <label>
            Spot (F proxy)
            <input value={spot} onChange={(e) => setSpot(e.target.value)} />
          </label>
          <label>
            n_k
            <input value={nK} onChange={(e) => setNK(e.target.value)} />
          </label>
          <label>
            n_t
            <input value={nT} onChange={(e) => setNT(e.target.value)} />
          </label>
          <button type="button" disabled={!canCompute} onClick={onCompute}>
            Compute
          </button>
          <button type="button" disabled={!surfaceId} onClick={downloadParquet}>
            Download Parquet
          </button>
        </div>
      </div>

      {error ? <div className="error panel">{error}</div> : null}

      {assumptions ? (
        <div className="panel">
          <h2 style={{ marginTop: 0 }}>Assumptions</h2>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, color: "var(--muted)", fontSize: 13 }}>
            {JSON.stringify(assumptions, null, 2)}
          </pre>
        </div>
      ) : null}

      {chart ? <SurfaceCharts chart={chart} /> : null}
    </main>
  );
}
