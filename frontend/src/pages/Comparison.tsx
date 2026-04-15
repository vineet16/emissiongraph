/**
 * Comparison page — Spatial flow (spec 9.3).
 * Two ports side by side. Intensity numbers at top, attribution breakdown
 * in middle, narrative at bottom. Click any number -> cell drill-down.
 */

import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts";
import type { AttributionTree } from "../api";
import { getSpatial, getNarrative, NarrativeResponse } from "../api";
import CellDrillDown from "../components/CellDrillDown";

export default function Comparison() {
  const { portA, portB } = useParams<{ portA: string; portB: string }>();
  const navigate = useNavigate();
  const [tree, setTree] = useState<AttributionTree | null>(null);
  const [narrative, setNarrative] = useState<NarrativeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drillDown, setDrillDown] = useState<{
    isOpen: boolean;
    value: number;
    label: string;
  }>({ isOpen: false, value: 0, label: "" });

  const fy = "FY24-25";

  useEffect(() => {
    if (!portA || !portB) return;
    setLoading(true);
    setError(null);
    getSpatial(portA, portB, fy)
      .then((t) => {
        setTree(t);
        // Try to get narrative
        return getNarrative(t.graph_hash).catch(() => null);
      })
      .then((n) => {
        if (n) setNarrative(n);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [portA, portB]);

  const children = tree?.children ?? [];

  const chartData = children.map((c) => ({
    name: c.label,
    contribution: Number(c.delta_value.toFixed(6)),
    pct: Number(Math.abs(c.delta_pct_of_gap).toFixed(1)),
  }));

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => navigate("/")}
          className="text-muted-foreground hover:text-foreground"
        >
          &larr; Fleet
        </button>
        <h1 className="text-xl font-bold">
          {portA} vs {portB} — Spatial Comparison
        </h1>
        <span className="text-sm text-muted-foreground">{fy}</span>
      </header>

      <main className="max-w-6xl mx-auto p-6 space-y-6">
        {loading && (
          <div className="text-center py-12 text-muted-foreground">
            Running spatial attribution...
          </div>
        )}

        {error && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 text-destructive text-sm">
            {error}
          </div>
        )}

        {tree && !loading && (
          <>
            {/* Side-by-side intensity comparison */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white rounded-lg border p-6 text-center">
                <div className="text-sm text-muted-foreground mb-1">
                  {portA}
                </div>
                <div
                  className="text-3xl font-mono font-bold cursor-pointer hover:text-primary"
                  onClick={() =>
                    setDrillDown({
                      isOpen: true,
                      value: tree.root_value_a,
                      label: `${portA} Emission Intensity`,
                    })
                  }
                >
                  {tree.root_value_a.toFixed(4)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  tCO2e/MT
                </div>
              </div>
              <div className="bg-white rounded-lg border p-6 text-center">
                <div className="text-sm text-muted-foreground mb-1">Gap</div>
                <div
                  className={`text-3xl font-mono font-bold ${
                    tree.root_gap > 0 ? "text-red-600" : "text-green-600"
                  }`}
                >
                  {tree.root_gap > 0 ? "+" : ""}
                  {tree.root_gap.toFixed(4)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {tree.root_gap_pct.toFixed(1)}%
                </div>
              </div>
              <div className="bg-white rounded-lg border p-6 text-center">
                <div className="text-sm text-muted-foreground mb-1">
                  {portB}
                </div>
                <div
                  className="text-3xl font-mono font-bold cursor-pointer hover:text-primary"
                  onClick={() =>
                    setDrillDown({
                      isOpen: true,
                      value: tree.root_value_b,
                      label: `${portB} Emission Intensity`,
                    })
                  }
                >
                  {tree.root_value_b.toFixed(4)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  tCO2e/MT
                </div>
              </div>
            </div>

            {/* Attribution breakdown chart */}
            <div className="bg-white rounded-lg border p-4">
              <h2 className="text-sm font-medium text-muted-foreground mb-4">
                Attribution Breakdown — Contribution to Intensity Gap
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="name"
                    angle={-30}
                    textAnchor="end"
                    height={80}
                  />
                  <YAxis />
                  <Tooltip
                    formatter={(value: number) => [
                      value.toFixed(6),
                      "Contribution (tCO2e/MT)",
                    ]}
                  />
                  <Bar dataKey="contribution" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={entry.contribution > 0 ? "#ef4444" : "#22c55e"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Narrative */}
            {narrative && narrative.validator_passed && (
              <div className="bg-white rounded-lg border p-4">
                <h2 className="text-sm font-medium text-muted-foreground mb-2">
                  Attribution Narrative
                </h2>
                <p className="text-sm text-gray-700 leading-relaxed">
                  {narrative.narrative}
                </p>
              </div>
            )}

            {/* Detailed attribution table */}
            <div className="bg-white rounded-lg border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-3 text-left">Source</th>
                    <th className="px-4 py-3 text-right">
                      Contribution (tCO2e/MT)
                    </th>
                    <th className="px-4 py-3 text-right">% of Gap</th>
                    <th className="px-4 py-3 text-right">Direction</th>
                  </tr>
                </thead>
                <tbody>
                  {children.map((c, i) => (
                    <React.Fragment key={i}>
                      <tr className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium">{c.label}</td>
                        <td
                          className="px-4 py-3 text-right font-mono cursor-pointer hover:text-primary"
                          onClick={() =>
                            setDrillDown({
                              isOpen: true,
                              value: c.delta_value,
                              label: `${c.label} gap contribution`,
                            })
                          }
                        >
                          {c.delta_value.toFixed(6)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {c.delta_pct_of_gap.toFixed(1)}%
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span
                            className={
                              c.direction === "increase"
                                ? "text-red-600"
                                : "text-green-600"
                            }
                          >
                            {c.direction}
                          </span>
                        </td>
                      </tr>
                      {c.children.map((sub, j) => (
                        <React.Fragment key={`${i}-${j}`}>
                          <tr className="border-b bg-gray-50/50">
                            <td className="px-4 py-2 pl-8 text-muted-foreground">
                              {sub.label}
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-muted-foreground">
                              {sub.delta_value.toFixed(6)}
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-muted-foreground">
                              {sub.delta_pct_of_gap.toFixed(1)}%
                            </td>
                            <td className="px-4 py-2 text-right text-muted-foreground">
                              {sub.direction}
                            </td>
                          </tr>
                          {sub.children.map((subsub, k) => (
                            <tr
                              key={`${i}-${j}-${k}`}
                              className="border-b bg-gray-50/30"
                            >
                              <td className="px-4 py-2 pl-12 text-muted-foreground text-xs">
                                {subsub.label}
                              </td>
                              <td className="px-4 py-2 text-right font-mono text-muted-foreground text-xs">
                                {subsub.delta_value.toFixed(6)}
                              </td>
                              <td className="px-4 py-2 text-right font-mono text-muted-foreground text-xs">
                                {subsub.delta_pct_of_gap.toFixed(1)}%
                              </td>
                              <td className="px-4 py-2 text-right text-muted-foreground text-xs">
                                {subsub.direction}
                              </td>
                            </tr>
                          ))}
                        </React.Fragment>
                      ))}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Excluded sources */}
            {tree.excluded_sources && tree.excluded_sources.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
                Note: {tree.excluded_sources.join(", ")} excluded from monthly
                attribution (annual-only sources).
              </div>
            )}
          </>
        )}
      </main>

      <CellDrillDown
        isOpen={drillDown.isOpen}
        onClose={() => setDrillDown({ ...drillDown, isOpen: false })}
        value={drillDown.value}
        label={drillDown.label}
      />
    </div>
  );
}
