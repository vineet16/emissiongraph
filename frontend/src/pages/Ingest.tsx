import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadWorkbook, buildGraph } from "../api";

const FY_OPTIONS = ["FY24-25", "FY23-24", "FY22-23"];

export default function Ingest() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [portId, setPortId] = useState("P1");
  const [fy, setFy] = useState(FY_OPTIONS[0]);
  const [status, setStatus] = useState<"idle" | "uploading" | "building" | "done" | "error">("idle");
  const [result, setResult] = useState<string>("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    try {
      setStatus("uploading");
      const ingestResult = await uploadWorkbook(file, portId, fy);
      setResult(
        `Ingested ${ingestResult.measurement_count} measurements (hash: ${ingestResult.fact_hash.slice(0, 12)}…)`
      );

      setStatus("building");
      const graphResult = await buildGraph(portId, fy);
      setResult(
        `Ingested ${ingestResult.measurement_count} measurements (hash: ${ingestResult.fact_hash.slice(0, 12)}…)\nGraph built: ${graphResult.node_count} nodes, intensity = ${graphResult.emission_intensity.toFixed(2)} tCO₂/MT`
      );

      setStatus("done");
    } catch (err: any) {
      setStatus("error");
      setResult(err.message || "Upload failed");
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Ingest Workbook</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Excel workbook (.xlsx)</label>
            <input
              type="file"
              accept=".xlsx,.xls"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-blue-600 file:text-white file:cursor-pointer hover:file:bg-blue-500"
            />
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block text-sm text-gray-400 mb-1">Port ID</label>
              <input
                type="text"
                value={portId}
                onChange={(e) => setPortId(e.target.value)}
                className="w-full rounded bg-gray-800 border border-gray-700 px-3 py-2 text-sm"
              />
            </div>
            <div className="flex-1">
              <label className="block text-sm text-gray-400 mb-1">Fiscal Year</label>
              <select
                value={fy}
                onChange={(e) => setFy(e.target.value)}
                className="w-full rounded bg-gray-800 border border-gray-700 px-3 py-2 text-sm"
              >
                {FY_OPTIONS.map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="submit"
            disabled={!file || status === "uploading" || status === "building"}
            className="w-full py-2 px-4 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed font-medium"
          >
            {status === "uploading"
              ? "Uploading…"
              : status === "building"
              ? "Building graph…"
              : "Upload & Build Graph"}
          </button>
        </form>

        {result && (
          <div
            className={`mt-6 p-4 rounded text-sm whitespace-pre-line ${
              status === "error"
                ? "bg-red-900/40 border border-red-700"
                : "bg-gray-800 border border-gray-700"
            }`}
          >
            {result}
          </div>
        )}

        {status === "done" && (
          <button
            onClick={() => navigate("/")}
            className="mt-4 w-full py-2 px-4 rounded bg-gray-700 hover:bg-gray-600 font-medium"
          >
            Go to Dashboard
          </button>
        )}
      </div>
    </div>
  );
}
