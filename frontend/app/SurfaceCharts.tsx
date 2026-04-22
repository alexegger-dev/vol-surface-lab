"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import type { Config, Data, Layout } from "plotly.js";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export type ChartPayload = {
  k: number[];
  t: number[];
  iv: (number | null)[][];
};

export function SurfaceCharts({ chart }: { chart: ChartPayload }) {
  const heatmap = useMemo(() => {
    const z = chart.iv.map((row) => row.map((v) => (v == null ? NaN : v)));
    return [
      {
        type: "heatmap" as const,
        x: chart.k,
        y: chart.t,
        z,
        colorscale: "Viridis" as const,
        colorbar: { title: { text: "IV" } },
        hovertemplate: "k=%{x}<br>T=%{y}<br>IV=%{z}<extra></extra>",
      },
    ] satisfies Data[];
  }, [chart]);

  const surface3d = useMemo(() => {
    const z = chart.iv.map((row) => row.map((v) => (v == null ? NaN : v)));
    return [
      {
        type: "surface" as const,
        x: chart.k,
        y: chart.t,
        z,
        colorscale: "Viridis" as const,
        colorbar: { title: { text: "IV" } },
        hovertemplate: "k=%{x}<br>T=%{y}<br>IV=%{z}<extra></extra>",
      },
    ] satisfies Data[];
  }, [chart]);

  const layoutHeat: Partial<Layout> = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { color: "#e8ecff" },
    margin: { l: 60, r: 20, t: 30, b: 50 },
    title: "IV heatmap (log-moneyness vs year fraction)",
    xaxis: { title: "log(K/F)" },
    yaxis: { title: "T (ACT/365F)" },
  };

  const layout3d: Partial<Layout> = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { color: "#e8ecff" },
    margin: { l: 0, r: 0, t: 30, b: 0 },
    title: "IV surface (3D)",
    scene: {
      xaxis: { title: "log(K/F)" },
      yaxis: { title: "T" },
      zaxis: { title: "IV" },
    },
  };

  const config: Partial<Config> = {
    displayModeBar: true,
    responsive: true,
    scrollZoom: true,
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div className="panel" style={{ minHeight: 420 }}>
        <Plot data={heatmap} layout={layoutHeat} config={config} style={{ width: "100%", height: 420 }} useResizeHandler />
      </div>
      <div className="panel" style={{ minHeight: 480 }}>
        <Plot data={surface3d} layout={layout3d} config={config} style={{ width: "100%", height: 480 }} useResizeHandler />
      </div>
    </div>
  );
}
