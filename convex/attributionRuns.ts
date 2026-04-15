import { query, mutation } from "./_generated/server";
import { v } from "convex/values";

export const byHash = query({
  args: { treeHash: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("attributionRuns")
      .withIndex("by_tree_hash", (q) => q.eq("treeHash", args.treeHash))
      .first();
  },
});

export const recent = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    const results = await ctx.db
      .query("attributionRuns")
      .order("desc")
      .take(args.limit ?? 20);
    return results;
  },
});

export const store = mutation({
  args: {
    runId: v.string(),
    queryType: v.union(
      v.literal("spatial"),
      v.literal("temporal"),
      v.literal("fleet")
    ),
    queryParams: v.any(),
    factHash: v.string(),
    graphHash: v.string(),
    treeHash: v.string(),
    treeJson: v.any(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("attributionRuns")
      .withIndex("by_tree_hash", (q) => q.eq("treeHash", args.treeHash))
      .first();

    if (existing) {
      return existing._id;
    }

    return await ctx.db.insert("attributionRuns", {
      ...args,
      createdAt: Date.now(),
    });
  },
});
