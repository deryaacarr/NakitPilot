"""Workflow versioning: draft / publish / archive (NP-216)."""

from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.workflows.enums import WorkflowLifecycleStatus
from apps.workflows.models import CollectionWorkflow, WorkflowEdge, WorkflowStep
from apps.workflows.services import WorkflowServiceError, serialize_graph


def new_workflow_key() -> str:
    return str(uuid.uuid4())


def clone_graph(source: CollectionWorkflow, target: CollectionWorkflow) -> None:
    """Copy steps + edges from source onto target (target graph must be empty)."""
    key_map: dict[int, WorkflowStep] = {}
    for step in source.steps.order_by("order", "id"):
        cloned = WorkflowStep.objects.create(
            organization=target.organization,
            workflow=target,
            name=step.name,
            step_type=step.step_type,
            config=step.config or {},
            order=step.order,
            position_x=step.position_x,
            position_y=step.position_y,
            is_active=step.is_active,
            stop_on_match=step.stop_on_match,
            client_key=step.client_key,
        )
        key_map[step.id] = cloned
    for edge in source.edges.select_related("from_step", "to_step"):
        WorkflowEdge.objects.create(
            organization=target.organization,
            workflow=target,
            from_step=key_map[edge.from_step_id],
            to_step=key_map[edge.to_step_id],
            source_handle=edge.source_handle,
        )
    target.canvas_meta = source.canvas_meta or {}
    target.save(update_fields=["canvas_meta", "updated_at"])


@transaction.atomic
def publish_workflow(workflow: CollectionWorkflow, *, actor=None) -> dict[str, Any]:
    """
    Publish a draft:
    1. Archive any currently published sibling (same workflow_key).
    2. Promote this draft → published (immutable).
    3. Create a new draft clone at version+1 for continued editing.
    """
    if workflow.status != WorkflowLifecycleStatus.DRAFT:
        raise WorkflowServiceError("Yalnızca taslak akışlar yayınlanabilir.", "not_draft")

    # Archive previous published versions in this family
    CollectionWorkflow.objects.filter(
        organization=workflow.organization,
        workflow_key=workflow.workflow_key,
        status=WorkflowLifecycleStatus.PUBLISHED,
    ).exclude(pk=workflow.pk).update(
        status=WorkflowLifecycleStatus.ARCHIVED,
        is_active=False,
        updated_at=timezone.now(),
    )

    workflow.status = WorkflowLifecycleStatus.PUBLISHED
    workflow.is_active = True
    workflow.published_at = timezone.now()
    workflow.published_by = actor
    workflow.save(
        update_fields=[
            "status",
            "is_active",
            "published_at",
            "published_by",
            "updated_at",
        ]
    )

    next_version = (
        CollectionWorkflow.objects.filter(
            organization=workflow.organization,
            workflow_key=workflow.workflow_key,
        ).order_by("-version").values_list("version", flat=True).first()
        or workflow.version
    ) + 1

    draft = CollectionWorkflow.objects.create(
        organization=workflow.organization,
        name=workflow.name,
        description=workflow.description,
        trigger_type=workflow.trigger_type,
        status=WorkflowLifecycleStatus.DRAFT,
        workflow_key=workflow.workflow_key,
        version=next_version,
        is_active=False,
        priority=workflow.priority,
        created_by=actor or workflow.created_by,
    )
    clone_graph(workflow, draft)

    return {"published": workflow, "draft": draft}


@transaction.atomic
def archive_workflow(workflow: CollectionWorkflow) -> CollectionWorkflow:
    workflow.status = WorkflowLifecycleStatus.ARCHIVED
    workflow.is_active = False
    workflow.save(update_fields=["status", "is_active", "updated_at"])
    return workflow


def ensure_editable(workflow: CollectionWorkflow) -> None:
    if not workflow.is_editable:
        raise WorkflowServiceError(
            "Yayınlanmış veya arşivlenmiş akış düzenlenemez. Taslak sürümü kullanın.",
            "not_editable",
        )


def list_family_versions(workflow: CollectionWorkflow) -> list[CollectionWorkflow]:
    return list(
        CollectionWorkflow.objects.filter(
            organization=workflow.organization,
            workflow_key=workflow.workflow_key,
        ).order_by("-version")
    )
