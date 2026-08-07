"use client";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type OnConnect,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  archiveWorkflow,
  getWorkflow,
  getWorkflowMeta,
  publishWorkflow,
  saveWorkflowGraph,
  simulateWorkflow,
  statusLabel,
  updateWorkflow,
  type WorkflowDetail,
  type WorkflowMeta,
  type WorkflowSimulation,
} from "@/lib/workflows/api";
import { WorkflowBlockNode, type WorkflowNodeData } from "./workflow-block-node";

const nodeTypes = { workflowBlock: WorkflowBlockNode };

const PALETTE = [
  { type: "condition", label: "Condition" },
  { type: "delay", label: "Delay" },
  { type: "action", label: "Action" },
  { type: "branch", label: "Branch" },
  { type: "stop", label: "Stop" },
] as const;

function summaryFor(stepType: string, config: Record<string, unknown>): string {
  if (stepType === "action") return String(config.action_type ?? "aksiyon");
  if (stepType === "delay") return `${config.amount ?? "?"} ${config.unit ?? "business_days"}`;
  if (stepType === "condition" || stepType === "branch") {
    const expr = config.expression as { all?: unknown[]; any?: unknown[] } | undefined;
    if (expr?.all) return `all (${expr.all.length})`;
    if (expr?.any) return `any (${expr.any.length})`;
    return "koşul";
  }
  return "";
}

function toFlow(detail: WorkflowDetail): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = detail.graph.steps.map((s) => ({
    id: s.client_key,
    type: "workflowBlock",
    position: { x: s.position_x, y: s.position_y },
    data: {
      label: s.name,
      stepType: s.step_type,
      summary: summaryFor(s.step_type, s.config || {}),
      config: s.config || {},
    } as WorkflowNodeData & { config: Record<string, unknown> },
  }));
  const edges: Edge[] = detail.graph.edges.map((e, i) => ({
    id: `e-${e.id ?? i}`,
    source: e.source,
    target: e.target,
    sourceHandle: e.source_handle === "next" ? "next" : e.source_handle,
    label: e.source_handle !== "next" ? e.source_handle : undefined,
  }));
  return { nodes, edges };
}

export function WorkflowBuilderView({ workflowId }: { workflowId: string }) {
  const { toast } = useToast();
  const [detail, setDetail] = useState<WorkflowDetail | null>(null);
  const [meta, setMeta] = useState<WorkflowMeta | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [simulation, setSimulation] = useState<WorkflowSimulation | null>(null);
  const [simulating, setSimulating] = useState(false);

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedId) ?? null,
    [nodes, selectedId],
  );

  const load = useCallback(async () => {
    const [wfRes, metaRes] = await Promise.all([getWorkflow(workflowId), getWorkflowMeta()]);
    if (!wfRes.ok) {
      toast({ title: "Yüklenemedi", description: wfRes.error.message, tone: "error" });
      return;
    }
    setDetail(wfRes.data);
    setName(wfRes.data.name);
    const flow = toFlow(wfRes.data);
    setNodes(flow.nodes);
    setEdges(flow.edges);
    if (metaRes.ok) setMeta(metaRes.data);
  }, [workflowId, setNodes, setEdges, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            sourceHandle: connection.sourceHandle ?? "next",
          },
          eds,
        ),
      );
    },
    [setEdges],
  );

  function addBlock(stepType: string) {
    const id = `${stepType}-${Date.now()}`;
    const config: Record<string, unknown> =
      stepType === "delay"
        ? { amount: 3, unit: "business_days" }
        : stepType === "action"
          ? { action_type: "create_task", params: { task_type: "CALL", title: "Yeni görev" } }
          : stepType === "condition" || stepType === "branch"
            ? {
                expression: {
                  all: [{ field: "invoice.overdue_days", operator: "greater_than", value: 7 }],
                },
              }
            : {};
    setNodes((nds) => [
      ...nds,
      {
        id,
        type: "workflowBlock",
        position: { x: 120 + nds.length * 40, y: 120 + nds.length * 30 },
        data: {
          label: stepType.charAt(0).toUpperCase() + stepType.slice(1),
          stepType,
          summary: summaryFor(stepType, config),
          config,
        },
      },
    ]);
    setSelectedId(id);
  }

  function patchSelected(patch: Partial<WorkflowNodeData> & { config?: Record<string, unknown> }) {
    if (!selectedId) return;
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id !== selectedId) return n;
        const data = {
          ...(n.data as WorkflowNodeData & { config: Record<string, unknown> }),
          ...patch,
        };
        if (patch.config) {
          data.config = { ...data.config, ...patch.config };
          data.summary = summaryFor(data.stepType, data.config);
        }
        return { ...n, data };
      }),
    );
  }

  async function onSave() {
    setSaving(true);
    const upd = await updateWorkflow(workflowId, { name });
    if (!upd.ok) {
      toast({ title: "Kayıt başarısız", description: upd.error.message, tone: "error" });
      setSaving(false);
      return;
    }
    const steps = nodes.map((n, i) => {
      const data = n.data as WorkflowNodeData & { config: Record<string, unknown> };
      return {
        client_key: n.id,
        name: data.label,
        step_type: data.stepType,
        config: data.config || {},
        position_x: n.position.x,
        position_y: n.position.y,
        order: i,
      };
    });
    const graphEdges = edges.map((e) => ({
      source: e.source,
      target: e.target,
      source_handle: (e.sourceHandle as string) || "next",
    }));
    const saved = await saveWorkflowGraph(workflowId, { steps, edges: graphEdges });
    setSaving(false);
    if (!saved.ok) {
      toast({ title: "Graf kaydı başarısız", description: saved.error.message, tone: "error" });
      return;
    }
    setDetail(saved.data);
    toast({ title: "Akış kaydedildi", tone: "success" });
  }

  async function onPublish() {
    if (!detail) return;
    const res = await publishWorkflow(workflowId);
    if (!res.ok) {
      toast({ title: "Yayınlanamadı", description: res.error.message, tone: "error" });
      return;
    }
    toast({
      title: `v${res.data.published.version} yayınlandı`,
      description: `Yeni taslak v${res.data.draft.version} oluşturuldu.`,
      tone: "success",
    });
    window.location.href = `/dashboard/workflows/${res.data.draft.id}`;
  }

  async function onArchive() {
    if (!detail) return;
    const res = await archiveWorkflow(workflowId);
    if (!res.ok) {
      toast({ title: "Arşivlenemedi", description: res.error.message, tone: "error" });
      return;
    }
    setDetail({ ...detail, ...res.data, graph: detail.graph });
    toast({ title: "Arşivlendi", tone: "success" });
  }

  async function onSimulate() {
    setSimulating(true);
    const res = await simulateWorkflow(workflowId, { days: 30 });
    setSimulating(false);
    if (!res.ok) {
      toast({ title: "Simülasyon başarısız", description: res.error.message, tone: "error" });
      return;
    }
    setSimulation(res.data);
  }

  if (!detail) {
    return <div className="p-6 text-sm text-slate-600">Yükleniyor…</div>;
  }

  const selectedData = selectedNode
    ? (selectedNode.data as WorkflowNodeData & { config: Record<string, unknown> })
    : null;

  const delayUnits = (meta?.delay_units ?? ["business_days", "days", "hours"]).map((u) => ({
    value: u,
    label: u,
  }));
  const actionOptions = (meta?.action_types ?? []).map((a) => ({
    value: a.value,
    label: a.label,
  }));
  const editable = detail.status === "draft";

  return (
    <div className="flex h-[calc(100vh-8rem)] min-h-[520px] flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          className="max-w-xs"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={!editable}
        />
        <Button type="button" onClick={() => void onSave()} disabled={saving || !editable}>
          {saving ? "Kaydediliyor…" : "Kaydet"}
        </Button>
        {detail.status === "draft" ? (
          <Button type="button" onClick={() => void onPublish()}>
            Yayınla
          </Button>
        ) : null}
        {detail.status !== "archived" ? (
          <Button type="button" variant="secondary" onClick={() => void onArchive()}>
            Arşivle
          </Button>
        ) : null}
        <Button type="button" variant="outline" onClick={() => void onSimulate()} disabled={simulating}>
          {simulating ? "Simüle ediliyor…" : "Son 30 günü simüle et"}
        </Button>
        <span className="text-xs text-slate-500">
          {statusLabel(detail.status)} · v{detail.version} ·{" "}
          {meta?.triggers.find((t) => t.value === detail.trigger_type)?.label ?? detail.trigger_type}
        </span>
      </div>

      {simulation ? (
        <div className="rounded-md border border-teal-200 bg-teal-50/70 px-4 py-3 text-sm text-teal-950">
          <p className="font-medium">{simulation.headline}</p>
          <p className="mt-1 text-xs text-teal-900/80">
            {simulation.events_evaluated} olay değerlendirildi · {simulation.tasks_created} görev ·{" "}
            {simulation.customers_messaged} müşteri mesajı · {simulation.critical_notifications} kritik
            bildirim
          </p>
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1 gap-3">
        <aside className="w-40 shrink-0 space-y-2 border-r border-slate-200 pr-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bloklar</p>
          <div className="space-y-1.5">
            {PALETTE.map((p) => (
              <button
                key={p.type}
                type="button"
                disabled={!editable}
                onClick={() => addBlock(p.type)}
                className="w-full rounded border border-slate-200 bg-white px-2 py-1.5 text-left text-sm text-slate-800 hover:border-teal-600 hover:bg-teal-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {p.label}
              </button>
            ))}
          </div>
          {!editable ? (
            <p className="pt-2 text-[11px] leading-snug text-amber-800">
              Bu sürüm düzenlenemez. Yayın sonrası oluşan taslağı açın.
            </p>
          ) : (
            <p className="pt-2 text-[11px] leading-snug text-slate-500">
              Trigger zaten var. Branch için true/false tutamaçlarından bağlayın.
            </p>
          )}
        </aside>

        <div className="min-w-0 flex-1 overflow-hidden rounded-md border border-slate-200 bg-[radial-gradient(circle_at_top_left,#ecfdf5,transparent_50%),linear-gradient(180deg,#f8fafc,#f1f5f9)]">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            onSelectionChange={({ nodes: sel }) => setSelectedId(sel[0]?.id ?? null)}
            fitView
            deleteKeyCode={["Backspace", "Delete"]}
          >
            <Background gap={18} size={1} />
            <Controls />
            <MiniMap pannable zoomable />
          </ReactFlow>
        </div>

        <aside className="w-72 shrink-0 overflow-y-auto border-l border-slate-200 pl-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Özellikler</p>
          {!selectedData ? (
            <p className="mt-3 text-sm text-slate-600">Bir blok seçin.</p>
          ) : (
            <div className="mt-3 space-y-3 text-sm">
              <label className="block">
                <span className="mb-1 block text-slate-600">Ad</span>
                <Input
                  value={selectedData.label}
                  onChange={(e) => patchSelected({ label: e.target.value })}
                />
              </label>
              <div className="text-xs text-slate-500">Tip: {selectedData.stepType}</div>

              {selectedData.stepType === "delay" ? (
                <>
                  <label className="block">
                    <span className="mb-1 block text-slate-600">Süre</span>
                    <Input
                      type="number"
                      value={Number(selectedData.config.amount ?? 1)}
                      onChange={(e) =>
                        patchSelected({
                          config: { ...selectedData.config, amount: Number(e.target.value) },
                        })
                      }
                    />
                  </label>
                  <Select
                    label="Birim"
                    value={String(selectedData.config.unit ?? "business_days")}
                    onChange={(e) =>
                      patchSelected({
                        config: { ...selectedData.config, unit: e.target.value },
                      })
                    }
                    options={delayUnits}
                  />
                </>
              ) : null}

              {selectedData.stepType === "action" ? (
                <>
                  <Select
                    label="Aksiyon"
                    value={String(selectedData.config.action_type ?? "create_task")}
                    onChange={(e) =>
                      patchSelected({
                        config: {
                          ...selectedData.config,
                          action_type: e.target.value,
                          params: (selectedData.config.params as object) || {},
                        },
                      })
                    }
                    options={
                      actionOptions.length
                        ? actionOptions
                        : [{ value: "create_task", label: "Görev oluştur" }]
                    }
                  />
                  <label className="block">
                    <span className="mb-1 block text-slate-600">Params (JSON)</span>
                    <textarea
                      className="min-h-28 w-full rounded border border-slate-200 bg-white p-2 font-mono text-xs"
                      value={JSON.stringify(selectedData.config.params ?? {}, null, 2)}
                      onChange={(e) => {
                        try {
                          const params = JSON.parse(e.target.value);
                          patchSelected({ config: { ...selectedData.config, params } });
                        } catch {
                          /* ignore while typing */
                        }
                      }}
                    />
                  </label>
                </>
              ) : null}

              {selectedData.stepType === "condition" || selectedData.stepType === "branch" ? (
                <label className="block">
                  <span className="mb-1 block text-slate-600">Expression (JSON)</span>
                  <textarea
                    className="min-h-36 w-full rounded border border-slate-200 bg-white p-2 font-mono text-xs"
                    value={JSON.stringify(selectedData.config.expression ?? { all: [] }, null, 2)}
                    onChange={(e) => {
                      try {
                        const expression = JSON.parse(e.target.value);
                        patchSelected({ config: { ...selectedData.config, expression } });
                      } catch {
                        /* ignore */
                      }
                    }}
                  />
                </label>
              ) : null}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
