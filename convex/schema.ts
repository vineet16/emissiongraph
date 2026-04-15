import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  ports: defineTable({
    portId: v.string(),
    name: v.string(),
    location: v.optional(v.string()),
  }).index("by_port_id", ["portId"]),

  workbookUploads: defineTable({
    portId: v.string(),
    fy: v.string(),
    filename: v.string(),
    sha256: v.string(),
    storageId: v.id("_storage"),
    uploadedAt: v.number(),
  }).index("by_port_fy", ["portId", "fy"]),

  measurements: defineTable({
    measurementId: v.string(),
    portId: v.string(),
    fy: v.string(),
    period: v.union(v.literal("monthly"), v.literal("annual")),
    periodValue: v.string(),
    fuelType: v.string(),
    subType: v.optional(v.string()),
    measure: v.union(v.literal("consumption"), v.literal("fugitive_release")),
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
    .index("by_port_fy_period", ["portId", "fy", "periodValue"])
    .index("by_fuel", ["fuelType"])
    .index("by_measurement_id", ["measurementId"]),

  fuelRegistry: defineTable({
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
  }).index("by_fuel_period", ["fuelType", "applicableFrom"]),

  attributionRuns: defineTable({
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
    createdAt: v.number(),
  }).index("by_tree_hash", ["treeHash"]),

  narratives: defineTable({
    treeHash: v.string(),
    templateVersion: v.string(),
    narrative: v.string(),
    validatorPassed: v.boolean(),
    generatedAt: v.number(),
  }).index("by_tree_template", ["treeHash", "templateVersion"]),
});
