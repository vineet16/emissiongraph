import { query, mutation } from "./_generated/server";
import { v } from "convex/values";

export const byTreeHash = query({
  args: {
    treeHash: v.string(),
    templateVersion: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    if (args.templateVersion) {
      return await ctx.db
        .query("narratives")
        .withIndex("by_tree_template", (q) =>
          q.eq("treeHash", args.treeHash).eq("templateVersion", args.templateVersion)
        )
        .first();
    }
    return await ctx.db
      .query("narratives")
      .withIndex("by_tree_template", (q) => q.eq("treeHash", args.treeHash))
      .first();
  },
});

export const store = mutation({
  args: {
    treeHash: v.string(),
    templateVersion: v.string(),
    narrative: v.string(),
    validatorPassed: v.boolean(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("narratives")
      .withIndex("by_tree_template", (q) =>
        q.eq("treeHash", args.treeHash).eq("templateVersion", args.templateVersion)
      )
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        narrative: args.narrative,
        validatorPassed: args.validatorPassed,
        generatedAt: Date.now(),
      });
      return existing._id;
    }

    return await ctx.db.insert("narratives", {
      ...args,
      generatedAt: Date.now(),
    });
  },
});
