import { query, mutation } from "./_generated/server";
import { v } from "convex/values";

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("fuelRegistry").collect();
  },
});

export const byFuelType = query({
  args: { fuelType: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("fuelRegistry")
      .withIndex("by_fuel_period", (q) => q.eq("fuelType", args.fuelType))
      .collect();
  },
});

export const seed = mutation({
  args: {
    entries: v.array(
      v.object({
        fuelType: v.string(),
        defaultUnit: v.string(),
        energyFactorGjPerUnit: v.number(),
        scope1FactorTco2PerUnit: v.optional(v.number()),
        scope2FactorTco2PerUnit: v.optional(v.number()),
        ch4Factor: v.optional(v.number()),
        n2oFactor: v.optional(v.number()),
        gwp: v.optional(v.number()),
        applicableFrom: v.string(),
        applicableTo: v.optional(v.string()),
        sourceReference: v.string(),
      })
    ),
  },
  handler: async (ctx, args) => {
    let count = 0;
    for (const entry of args.entries) {
      const existing = await ctx.db
        .query("fuelRegistry")
        .withIndex("by_fuel_period", (q) =>
          q.eq("fuelType", entry.fuelType).eq("applicableFrom", entry.applicableFrom)
        )
        .first();

      if (!existing) {
        await ctx.db.insert("fuelRegistry", entry);
        count++;
      }
    }
    return { seeded: count };
  },
});
