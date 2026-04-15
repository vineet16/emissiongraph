import { action } from "../_generated/server";
import { v } from "convex/values";

const COMPUTE_URL = process.env.COMPUTE_SERVICE_URL ?? "http://localhost:8000";

export const spatial = action({
  args: {
    portA: v.string(),
    portB: v.string(),
    fy: v.string(),
    metric: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const response = await fetch(`${COMPUTE_URL}/attribution/spatial`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        port_a: args.portA,
        port_b: args.portB,
        fy: args.fy,
        metric: args.metric ?? "emission_intensity",
      }),
    });

    if (!response.ok) {
      throw new Error(
        `Attribution failed: ${response.status} ${await response.text()}`
      );
    }

    const tree = await response.json();

    // Store the attribution run in Convex
    await ctx.runMutation("attributionRuns:store" as any, {
      runId: tree.graph_hash,
      queryType: "spatial" as const,
      queryParams: { portA: args.portA, portB: args.portB, fy: args.fy },
      factHash: tree.fact_hash,
      graphHash: tree.graph_hash,
      treeHash: tree.graph_hash, // tree.hash() on the Python side
      treeJson: tree,
    });

    return tree;
  },
});

export const temporal = action({
  args: {
    port: v.string(),
    fyA: v.string(),
    fyB: v.string(),
    metric: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const response = await fetch(`${COMPUTE_URL}/attribution/temporal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        port: args.port,
        fy_a: args.fyA,
        fy_b: args.fyB,
        metric: args.metric ?? "emission_intensity",
      }),
    });

    if (!response.ok) {
      throw new Error(
        `Attribution failed: ${response.status} ${await response.text()}`
      );
    }

    const tree = await response.json();

    await ctx.runMutation("attributionRuns:store" as any, {
      runId: tree.graph_hash,
      queryType: "temporal" as const,
      queryParams: { port: args.port, fyA: args.fyA, fyB: args.fyB },
      factHash: tree.fact_hash,
      graphHash: tree.graph_hash,
      treeHash: tree.graph_hash,
      treeJson: tree,
    });

    return tree;
  },
});

export const fleet = action({
  args: {
    fy: v.string(),
    metric: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const response = await fetch(`${COMPUTE_URL}/attribution/fleet`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fy: args.fy,
        metric: args.metric ?? "emission_intensity",
      }),
    });

    if (!response.ok) {
      throw new Error(
        `Attribution failed: ${response.status} ${await response.text()}`
      );
    }

    const tree = await response.json();

    await ctx.runMutation("attributionRuns:store" as any, {
      runId: tree.graph_hash,
      queryType: "fleet" as const,
      queryParams: { fy: args.fy },
      factHash: tree.fact_hash,
      graphHash: tree.graph_hash,
      treeHash: tree.graph_hash,
      treeJson: tree,
    });

    return tree;
  },
});
