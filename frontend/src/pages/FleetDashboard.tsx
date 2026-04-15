/**
 * Fleet Dashboard — default landing page (spec 9.1).
 * Monday morning view: fleet ranking, bar chart, narrative, port table.
 */

import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { AttributionTree, FleetDenominator, PortData } from "../api";
import { getFleet } from "../api";

const FY_OPTIONS = ["FY24-25", "FY23-24", "FY22-23"];

export default function FleetDashboard() {
  const navigate = useNavigate();
  const [fy, setFy] = useState("FY24-25");
  const [tree, setTree] = useState<AttributionTree | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPorts, setSelectedPorts] = useState<string[]>([]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getFleet(fy)
      .then(setTree)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [fy]);

  const denominator = tree?.denominator as FleetDenominator | undefined;
  const portDetails = denominator?.port_details ?? [];
  const fleetMedian = denominator?.fleet_median ?? 0;

  const chartData = portDetails
    .sort((a, b) => b.intensity - a.intensity)
    .map((p) => ({
      name: p.port_id,
      intensity: Number(p.intensity.toFixed(4)),
      cargo: p.cargo_mt,
    }));

  const togglePort = (portId: string) => {
    setSelectedPorts((prev) =>
      prev.includes(portId)
        ? prev.filter((p) => p !== portId)
        : prev.length < 2
          ? [...prev, portId]
          : [prev[1], portId]
    );
  };

  const canCompare = selectedPorts.length === 2;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Fleet Emissions Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            EmissionGraph — Port Infrastructure Emissions Attribution
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={fy}
            onChange={(e) => setFy(e.target.value)}
            className="border rounded-md px-3 py-1.5 text-sm"
          >
            {FY_OPTIONS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
          {canCompare && (
            <button
              onClick={() =>
                navigate(`/compare/${selectedPorts[0]}/${selectedPorts[1]}`)
              }
              className="bg-primary text-primary-foreground px-4 py-1.5 rounded-md text-sm font-medium hover:opacity-90"
            >
              Compare
            </button>
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {loading && (
          <div className="text-center py-12 text-muted-foreground">
            Loading fleet data...
          </div>
        )}

        {error && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 text-destructive text-sm">
            {error}
            <div className="mt-2 text-xs">
              Make sure the Python compute service is running on port 8000 and
              workbooks have been ingested.
            </div>
          </div>
        )}

        {tree && !loading && (
          <>
            {/* Fleet narrative */}
            <div className="bg-white rounded-lg border p-4">
              <p className="text-sm text-gray-700">
                Fleet emission intensity ranges from{" "}
                <strong>{tree.root_value_b.toFixed(4)}</strong> to{" "}
                <strong>{tree.root_value_a.toFixed(4)}</strong> tCO2e/MT across{" "}
                {tree.subjects.length} ports, with a median of{" "}
                <strong>{fleetMedian.toFixed(4)}</strong> tCO2e/MT and a spread
                of <strong>{tree.root_gap.toFixed(4)}</strong>.
              </p>
            </div>

            {/* Bar chart */}
            <div className="bg-white rounded-lg border p-4">
              <h2 className="text-sm font-medium text-muted-foreground mb-4">
                Emission Intensity by Port (tCO2e/MT)
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={chartData}
                  layout="vertical"
                  margin={{ left: 40, right: 20, top: 5, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" domain={[0, "auto"]} />
                  <YAxis type="category" dataKey="name" width={40} />
                  <Tooltip
                    formatter={(value: number) => [
                      value.toFixed(4),
                      "Intensity",
                    ]}
                  />
                  <ReferenceLine
                    x={fleetMedian}
                    stroke="#94a3b8"
                    strokeDasharray="5 5"
                    label={{ value: "Median", position: "top" }}
                  />
                  <Bar dataKey="intensity" radius={[0, 4, 4, 0]}>
                    {chartData.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={
                          entry.intensity > fleetMedian ? "#ef4444" : "#22c55e"
                        }
                        fillOpacity={0.8}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Port table */}
            <div className="bg-white rounded-lg border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-3 text-left w-8"></th>
                    <th className="px-4 py-3 text-left">Port</th>
                    <th className="px-4 py-3 text-right">Cargo (MT)</th>
                    <th className="px-4 py-3 text-right">Scope 1 (tCO2e)</th>
                    <th className="px-4 py-3 text-right">Scope 2 (tCO2e)</th>
                    <th className="px-4 py-3 text-right">
                      Intensity (tCO2e/MT)
                    </th>
                    <th className="px-4 py-3 text-right">YoY</th>
                  </tr>
                </thead>
                <tbody>
                  {portDetails
                    .sort((a, b) => b.intensity - a.intensity)
                    .map((p) => (
                      <tr
                        key={p.port_id}
                        className={`border-b hover:bg-gray-50 cursor-pointer ${
                          selectedPorts.includes(p.port_id) ? "bg-blue-50" : ""
                        }`}
                        onClick={() => togglePort(p.port_id)}
                        onDoubleClick={() => navigate(`/port/${p.port_id}`)}
                      >
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={selectedPorts.includes(p.port_id)}
                            onChange={() => togglePort(p.port_id)}
                            className="rounded"
                          />
                        </td>
                        <td className="px-4 py-3 font-medium">{p.port_id}</td>
                        <td className="px-4 py-3 text-right font-mono">
                          {p.cargo_mt.toLocaleString(undefined, {
                            maximumFractionDigits: 0,
                          })}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {p.scope1_tco2.toLocaleString(undefined, {
                            maximumFractionDigits: 0,
                          })}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {p.scope2_tco2.toLocaleString(undefined, {
                            maximumFractionDigits: 0,
                          })}
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-bold">
                          {p.intensity.toFixed(4)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {p.yoy_delta_pct != null ? (
                            <span
                              className={
                                p.yoy_delta_pct > 0
                                  ? "text-red-600"
                                  : "text-green-600"
                              }
                            >
                              {p.yoy_delta_pct > 0 ? "+" : ""}
                              {p.yoy_delta_pct.toFixed(1)}%
                            </span>
                          ) : (
                            <span className="text-gray-300">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
              <div className="px-4 py-2 text-xs text-muted-foreground bg-gray-50">
                Click row to select for comparison. Double-click to view port
                detail. Select two ports and click Compare.
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
