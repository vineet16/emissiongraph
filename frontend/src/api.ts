/**
 * API client for the EmissionGraph compute service.
 * In production, requests go through Convex Actions → FastAPI.
 * In dev, Vite proxies /api to localhost:8000.
 */

const BASE = "/api";

export interface PortData {
  port_id: string;
  intensity: number;
  cargo_mt: number;
  scope1_tco2: number;
  scope2_tco2: number;
  total_emissions: number;
  energy_gj: number;
  yoy_delta_pct: number | null;
}

export interface FleetDenominator {
  fleet_min: number;
  fleet_max: number;
  fleet_median: number;
  fleet_spread: number;
  port_details: PortData[];
  fleet_emission_breakdown: Record<string, number>;
}

export interface AttributionNode {
  label: string;
  delta_value: number;
  delta_pct_of_gap: number;
  direction: "increase" | "decrease";
  source_node_ids: string[];
  children: AttributionNode[];
}

export interface AttributionTree {
  query_type: "spatial" | "temporal" | "fleet";
  subjects: string[];
  root_metric: string;
  root_value_a: number;
  root_value_b: number;
  root_gap: number;
  root_gap_pct: number;
  children: AttributionNode[];
  excluded_sources: string[] | null;
  denominator: any;
  fact_hash: string;
  graph_hash: string;
}

export interface NarrativeResponse {
  tree_hash: string;
  template_version: string;
  narrative: string;
  validator_passed: boolean;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getFleet(fy: string): Promise<AttributionTree> {
  return fetchJson(`${BASE}/attribution/fleet`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fy, metric: "emission_intensity" }),
  });
}

export async function getSpatial(
  portA: string,
  portB: string,
  fy: string
): Promise<AttributionTree> {
  return fetchJson(`${BASE}/attribution/spatial`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ port_a: portA, port_b: portB, fy, metric: "emission_intensity" }),
  });
}

export async function getTemporal(
  port: string,
  fyA: string,
  fyB: string
): Promise<AttributionTree> {
  return fetchJson(`${BASE}/attribution/temporal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ port, fy_a: fyA, fy_b: fyB, metric: "emission_intensity" }),
  });
}

export async function getNarrative(treeHash: string): Promise<NarrativeResponse> {
  return fetchJson(`${BASE}/narrative/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tree_hash: treeHash }),
  });
}

export async function getAvailableData(): Promise<{ ports: Record<string, string[]> }> {
  return fetchJson(`${BASE}/data/ports`);
}

export async function uploadWorkbook(
  file: File,
  portId: string,
  fy: string
): Promise<{ port_id: string; fy: string; measurement_count: number; fact_hash: string }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("port_id", portId);
  formData.append("fy", fy);
  return fetchJson(`${BASE}/ingest/workbook?port_id=${portId}&fy=${fy}`, {
    method: "POST",
    body: formData,
  });
}

export async function buildGraph(
  portId: string,
  fy: string
): Promise<{ graph_hash: string; node_count: number; emission_intensity: number }> {
  return fetchJson(`${BASE}/graph/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ port_id: portId, fy }),
  });
}
