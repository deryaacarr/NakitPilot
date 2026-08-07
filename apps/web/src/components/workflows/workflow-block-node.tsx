"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

export type WorkflowNodeData = {
  label: string;
  stepType: string;
  summary?: string;
};

const COLORS: Record<string, string> = {
  trigger: "border-teal-700 bg-teal-50",
  condition: "border-amber-600 bg-amber-50",
  branch: "border-amber-700 bg-orange-50",
  delay: "border-sky-700 bg-sky-50",
  action: "border-slate-700 bg-white",
  stop: "border-rose-700 bg-rose-50",
};

export function WorkflowBlockNode({ data, selected }: NodeProps) {
  const d = data as WorkflowNodeData;
  const color = COLORS[d.stepType] ?? COLORS.action;
  const isBranch = d.stepType === "branch";
  const isTrigger = d.stepType === "trigger";
  const isStop = d.stepType === "stop";

  return (
    <div
      className={`min-w-[160px] max-w-[220px] rounded-md border-2 px-3 py-2 shadow-sm ${color} ${
        selected ? "ring-2 ring-teal-500 ring-offset-1" : ""
      }`}
    >
      {!isTrigger ? <Handle type="target" position={Position.Left} className="!bg-slate-500" /> : null}
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{d.stepType}</div>
      <div className="mt-0.5 text-sm font-medium text-slate-900">{d.label}</div>
      {d.summary ? <div className="mt-1 text-xs text-slate-600 line-clamp-2">{d.summary}</div> : null}
      {!isStop && !isBranch ? (
        <Handle type="source" position={Position.Right} id="next" className="!bg-teal-700" />
      ) : null}
      {isBranch ? (
        <>
          <Handle
            type="source"
            position={Position.Right}
            id="true"
            style={{ top: "35%" }}
            className="!bg-emerald-600"
          />
          <Handle
            type="source"
            position={Position.Right}
            id="false"
            style={{ top: "70%" }}
            className="!bg-rose-600"
          />
          <div className="mt-1 flex justify-between text-[9px] text-slate-500">
            <span>true</span>
            <span>false</span>
          </div>
        </>
      ) : null}
    </div>
  );
}
