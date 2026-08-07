"""Workflow graph services (NP-211)."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.workflows.enums import WorkflowEdgeHandle, WorkflowStepType
from apps.workflows.models import CollectionWorkflow, WorkflowEdge, WorkflowStep


class WorkflowServiceError(Exception):
    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.message = message
        self.code = code


def validate_graph(steps: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    if not steps:
        raise WorkflowServiceError("En az bir adım gerekli.", "empty_graph")

    keys = [s.get("client_key") or f"tmp-{i}" for i, s in enumerate(steps)]
    if len(keys) != len(set(keys)):
        raise WorkflowServiceError("client_key benzersiz olmalı.", "duplicate_key")

    triggers = [s for s in steps if s.get("step_type") == WorkflowStepType.TRIGGER]
    if len(triggers) > 1:
        raise WorkflowServiceError("Tek bir Trigger bloğu olmalı.", "multiple_triggers")

    key_set = set(keys)
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src not in key_set or tgt not in key_set:
            raise WorkflowServiceError("Kenar bilinmeyen adıma bağlanıyor.", "bad_edge")
        if src == tgt:
            raise WorkflowServiceError("Adım kendisine bağlanamaz.", "self_loop")
        handle = e.get("source_handle") or WorkflowEdgeHandle.NEXT
        if handle not in WorkflowEdgeHandle.values:
            raise WorkflowServiceError(f"Geçersiz handle: {handle}", "bad_handle")


@transaction.atomic
def replace_workflow_graph(
    workflow: CollectionWorkflow,
    *,
    steps: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    canvas_meta: dict[str, Any] | None = None,
) -> CollectionWorkflow:
    from apps.workflows.versioning import ensure_editable

    ensure_editable(workflow)
    validate_graph(steps, edges)

    # Wipe existing graph (conditions/actions/edges cascade from steps)
    workflow.edges.all().delete()
    workflow.steps.all().delete()

    key_to_step: dict[str, WorkflowStep] = {}
    for i, raw in enumerate(steps):
        client_key = raw.get("client_key") or f"node-{i}"
        step = WorkflowStep.objects.create(
            organization=workflow.organization,
            workflow=workflow,
            name=(raw.get("name") or raw.get("step_type") or "Adım")[:128],
            step_type=raw.get("step_type") or WorkflowStepType.ACTION,
            config=raw.get("config") or {},
            order=i,
            position_x=float(raw.get("position_x") or 0),
            position_y=float(raw.get("position_y") or 0),
            is_active=bool(raw.get("is_active", True)),
            stop_on_match=bool(raw.get("stop_on_match", False)),
            client_key=client_key[:64],
        )
        key_to_step[client_key] = step

    seen_handles: set[tuple[str, str]] = set()
    for raw in edges:
        src = raw["source"]
        tgt = raw["target"]
        handle = raw.get("source_handle") or WorkflowEdgeHandle.NEXT
        pair = (src, handle)
        if pair in seen_handles:
            raise WorkflowServiceError(
                f"Aynı çıkış birden fazla bağlanamaz: {src}/{handle}",
                "duplicate_handle",
            )
        seen_handles.add(pair)
        WorkflowEdge.objects.create(
            organization=workflow.organization,
            workflow=workflow,
            from_step=key_to_step[src],
            to_step=key_to_step[tgt],
            source_handle=handle,
        )

    if canvas_meta is not None:
        workflow.canvas_meta = canvas_meta
        workflow.save(update_fields=["canvas_meta", "updated_at"])

    return workflow


def serialize_graph(workflow: CollectionWorkflow) -> dict[str, Any]:
    steps = []
    for s in workflow.steps.order_by("order", "id"):
        steps.append(
            {
                "id": s.id,
                "client_key": s.client_key or f"step-{s.id}",
                "name": s.name,
                "step_type": s.step_type,
                "config": s.config or {},
                "order": s.order,
                "position_x": s.position_x,
                "position_y": s.position_y,
                "is_active": s.is_active,
                "stop_on_match": s.stop_on_match,
            }
        )
    key_by_id = {s["id"]: s["client_key"] for s in steps}
    edges = []
    for e in workflow.edges.select_related("from_step", "to_step"):
        edges.append(
            {
                "id": e.id,
                "source": key_by_id.get(e.from_step_id, f"step-{e.from_step_id}"),
                "target": key_by_id.get(e.to_step_id, f"step-{e.to_step_id}"),
                "source_handle": e.source_handle,
            }
        )
    return {
        "steps": steps,
        "edges": edges,
        "canvas_meta": workflow.canvas_meta or {},
    }
