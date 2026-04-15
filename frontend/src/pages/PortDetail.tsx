/**
 * Port Detail — Temporal flow (spec 9.2).
 * Single port across periods. Chart on top, narrative middle,
 * table of monthly/yearly metrics below.
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
} from "recharts";
import type { AttributionTree } from "../api";
import { getTemporal } from "../api";
import CellDrillDown from "../components/CellDrillDown";

export default function PortDetail() {
  const { portId } = useParams<{ portId: string }>();
  const navigate = useNavigate();
  const [tree, setTree] = useState<AttributionTree | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drillDown, setDrillDown] = useState<{
    isOpen: boolean;
    value: number;
    label: string;
  }>({ isOpen: false, value: 0, label: "" });

  const fyLater = "FY24-25";
  const fyEarlier = "FY23-24";

  useEffect(() => {
    if (!portId) return;
    setLoading(true);
    setError(null);
    getTemporal(portId, fyEarlier, fyLater)
      .then(setTree)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [portId]);

  const children = tree?.children ?? [];

  const chartData = children.map((c) => ({
    name: c.label,
    delta: Number(c.delta_value.toFixed(6)),
    pctOfGap: Number(c.delta_pct_of_gap.toFixed(1)),
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
          {portId} — Temporal Analysis
        </h1>
        <span className="text-sm text-muted-foreground">
          {fyEarlier} vs {fyLater}
        </span>
      </header>

      <main className="max-w-6xl mx-auto p-6 space-y-6">
        {loading && (
          <div className="text-center py-12 text-muted-foreground">
            Loading temporal attribution...
          </div>
        )}

        {error && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 text-destructive text-sm">
            {error}
          </div>
        )}

        {tree && !loading && (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-white rounded-lg border p-4">
                <div className="text-xs text-muted-foreground">
                  {fyEarlier} Intensity
                </div>
                <div
                  className="text-2xl font-mono font-bold mt-1 cursor-pointer hover:text-primary"
                  onClick={() =>
                    setDrillDown({
                      isOpen: true,
                      value: tree.root_value_a,
                      label: `${portId} ${fyEarlier} Emission Intensity`,
                    })
                  }
                >
                  {tree.root_value_a.toFixed(4)}
                </div>
                <div className="text-xs text-muted-foreground">tCO2e/MT</div>
              </div>
              <div className="bg-white rounded-lg border p-4">
                <div className="text-xs text-muted-foreground">
                  {fyLater} Intensity
                </div>
                <div
                  className="text-2xl font-mono font-bold mt-1 cursor-pointer hover:text-primary"
                  onClick={() =>
                    setDrillDown({
                      isOpen: true,
                      value: tree.root_value_b,
                      label: `${portId} ${fyLater} Emission Intensity`,
                    })
                  }
                >
                  {tree.root_value_b.toFixed(4)}
                </div>
                <div className="text-xs text-muted-foreground">tCO2e/MT</div>
              </div>
              <div className="bg-white rounded-lg border p-4">
                <div className="text-xs text-muted-foreground">Change</div>
                <div
                  className={`text-2xl font-mono font-bold mt-1 ${
                    tree.root_gap > 0 ? "text-red-600" : "text-green-600"
                  }`}
                >
                  {tree.root_gap > 0 ? "+" : ""}
                  {tree.root_gap.toFixed(4)}
                </div>
                <div className="text-xs text-muted-foreground">tCO2e/MT</div>
              </div>
              <div className="bg-white rounded-lg border p-4">
                <div className="text-xs text-muted-foreground">Change %</div>
                <div
                  className={`text-2xl font-mono font-bold mt-1 ${
                    tree.root_gap_pct > 0 ? "text-red-600" : "text-green-600"
                  }`}
                >
                  {tree.root_gap_pct > 0 ? "+" : ""}
                  {tree.root_gap_pct.toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Attribution chart */}
            <div className="bg-white rounded-lg border p-4">
              <h2 className="text-sm font-medium text-muted-foreground mb-4">
                Source Contributions to Intensity Change
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" angle={-30} textAnchor="end" height={80} />
                  <YAxis />
                  <Tooltip
                    formatter={(value: number) => [
                      value.toFixed(6),
                      "Delta (tCO2e/MT)",
                    ]}
                  />
                  <Bar dataKey="delta" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Attribution table */}
            <div className="bg-white rounded-lg border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-3 text-left">Source</th>
                    <th className="px-4 py-3 text-right">Delta (tCO2e/MT)</th>
                    <th className="px-4 py-3 text-right">% of Change</th>
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
                              label: `${c.label} contribution`,
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
                        <tr
                          key={`${i}-${j}`}
                          className="border-b bg-gray-50/50 hover:bg-gray-50"
                        >
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
                      ))}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Excluded sources disclosure */}
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
