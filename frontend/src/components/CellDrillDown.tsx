/**
 * Cell drill-down modal — the demo moment.
 * Shows the formula chain: e.g. 0.0173 = (78 - 51) × 2.68 × 0.001
 * Each input is clickable back to its own source.
 */

import React from "react";

interface CellDrillDownProps {
  isOpen: boolean;
  onClose: () => void;
  value: number;
  label: string;
  sourceCell?: {
    workbook: string;
    sheet: string;
    cell: string;
    row: number;
    col: number;
  };
  formulaChain?: {
    result: number;
    expression: string;
    inputs: { label: string; value: number; sourceCell?: any }[];
  };
}

export default function CellDrillDown({
  isOpen,
  onClose,
  value,
  label,
  sourceCell,
  formulaChain,
}: CellDrillDownProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Cell Drill-Down</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Value display */}
          <div className="text-center">
            <div className="text-3xl font-mono font-bold text-primary">
              {value.toFixed(4)}
            </div>
            <div className="text-sm text-muted-foreground mt-1">{label}</div>
          </div>

          {/* Source cell reference */}
          {sourceCell && (
            <div className="bg-muted rounded-lg p-4">
              <div className="text-sm font-medium text-muted-foreground mb-2">
                Source Cell
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Workbook:</span>{" "}
                  {sourceCell.workbook}
                </div>
                <div>
                  <span className="text-muted-foreground">Sheet:</span>{" "}
                  {sourceCell.sheet}
                </div>
                <div>
                  <span className="text-muted-foreground">Cell:</span>{" "}
                  <span className="font-mono font-bold text-primary">
                    {sourceCell.cell}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">Position:</span> Row{" "}
                  {sourceCell.row}, Col {sourceCell.col}
                </div>
              </div>
            </div>
          )}

          {/* Formula chain */}
          {formulaChain && (
            <div className="bg-muted rounded-lg p-4">
              <div className="text-sm font-medium text-muted-foreground mb-3">
                Formula Chain
              </div>
              <div className="font-mono text-center text-lg mb-4">
                {formulaChain.result.toFixed(4)} ={" "}
                {formulaChain.expression}
              </div>
              <div className="space-y-2">
                {formulaChain.inputs.map((input, i) => (
                  <button
                    key={i}
                    className="w-full text-left p-2 rounded hover:bg-white/50 transition flex justify-between items-center"
                  >
                    <span className="text-sm">{input.label}</span>
                    <span className="font-mono font-bold">
                      {input.value}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* If no source data available */}
          {!sourceCell && !formulaChain && (
            <div className="text-center text-muted-foreground py-8">
              Source provenance data not available for this value.
              <br />
              Ingest a workbook to enable cell-level tracing.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
