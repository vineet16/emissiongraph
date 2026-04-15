import { query, mutation } from "./_generated/server";
import { v } from "convex/values";

export const byPortFy = query({
  args: {
    portId: v.string(),
    fy: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("measurements")
      .withIndex("by_port_fy_period", (q) =>
        q.eq("portId", args.portId).eq("fy", args.fy)
      )
      .collect();
  },
});

export const byCell = query({
  args: {
    measurementId: v.string(),
  },
  handler: async (ctx, args) => {
    const results = await ctx.db
      .query("measurements")
      .withIndex("by_measurement_id", (q) =>
        q.eq("measurementId", args.measurementId)
      )
      .first();
    return results;
  },
});

export const upsertBatch = mutation({
  args: {
    measurements: v.array(
      v.object({
        measurementId: v.string(),
        portId: v.string(),
        fy: v.string(),
        period: v.union(v.literal("monthly"), v.literal("annual")),
        periodValue: v.string(),
        fuelType: v.string(),
        subType: v.optional(v.string()),
        measure: v.union(
          v.literal("consumption"),
          v.literal("fugitive_release")
        ),
        quantity: v.number(),
        unit: v.string(),
        sourceCell: v.object({
          workbook: v.string(),
          sheet: v.string(),
          cell: v.string(),
          row: v.number(),
          col: v.number(),
        }),
        confidence: v.union(
          v.literal("EXTRACTED"),
          v.literal("INFERRED"),
          v.literal("AMBIGUOUS")
        ),
      })
    ),
  },
  handler: async (ctx, args) => {
    let inserted = 0;
    let updated = 0;

    for (const m of args.measurements) {
      const existing = await ctx.db
        .query("measurements")
        .withIndex("by_measurement_id", (q) =>
          q.eq("measurementId", m.measurementId)
        )
        .first();

      if (existing) {
        await ctx.db.patch(existing._id, m);
        updated++;
      } else {
        await ctx.db.insert("measurements", m);
        inserted++;
      }
    }

    return { inserted, updated };
  },
});
