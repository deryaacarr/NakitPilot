"""Workflow REST API (NP-211)."""

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import Customer
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.models import OrganizationHoliday
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.workflows.engine import resume_execution, run_workflow
from apps.workflows.enums import (
    WorkflowApprovalStatus,
    WorkflowLifecycleStatus,
    WorkflowLogEvent,
    WorkflowStepType,
)
from apps.workflows.models import (
    CollectionWorkflow,
    WorkflowApprovalRequest,
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowStep,
)
from apps.workflows.serializers import (
    CollectionWorkflowCreateSerializer,
    CollectionWorkflowSerializer,
    OrganizationHolidaySerializer,
    WorkflowApprovalDecideSerializer,
    WorkflowApprovalSerializer,
    WorkflowDetailSerializer,
    WorkflowExecutionSerializer,
    WorkflowGraphSerializer,
    WorkflowSimulateSerializer,
    WorkflowTestRunSerializer,
    workflow_meta_payload,
)
from apps.workflows.services import WorkflowServiceError, replace_workflow_graph
from apps.workflows.simulate import simulate_workflow
from apps.workflows.versioning import (
    archive_workflow,
    list_family_versions,
    new_workflow_key,
    publish_workflow,
)

_TENANT_PERMS = [
    IsAuthenticated,
    RequireTenantContextPermission,
    HasOrganizationPermission,
]


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class WorkflowMetaView(APIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request, *args, **kwargs):
        return Response(workflow_meta_payload())


class WorkflowListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK
    pagination_class = StandardResultsSetPagination
    queryset = CollectionWorkflow.objects.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CollectionWorkflowCreateSerializer
        return CollectionWorkflowSerializer

    def create(self, request, *args, **kwargs):
        serializer = CollectionWorkflowCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = self.get_current_organization()
        data = serializer.validated_data
        wf = CollectionWorkflow.objects.create(
            organization=org,
            name=data["name"],
            description=data.get("description") or "",
            trigger_type=data["trigger_type"],
            status=WorkflowLifecycleStatus.DRAFT,
            workflow_key=new_workflow_key(),
            version=1,
            is_active=False,
            priority=data.get("priority", 100),
            created_by=request.user,
        )
        WorkflowStep.objects.create(
            organization=org,
            workflow=wf,
            name="Tetikleyici",
            step_type=WorkflowStepType.TRIGGER,
            order=0,
            position_x=80,
            position_y=160,
            client_key="trigger",
        )
        return Response(WorkflowDetailSerializer(wf).data, status=status.HTTP_201_CREATED)


class WorkflowDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK
    queryset = CollectionWorkflow.objects.prefetch_related("steps", "edges").all()
    serializer_class = WorkflowDetailSerializer

    def patch(self, request, *args, **kwargs):
        wf = self.get_object()
        if not wf.is_editable and any(
            f in request.data for f in ("name", "description", "trigger_type", "priority", "canvas_meta")
        ):
            return Response(
                {"detail": "Yayınlanmış/arşiv akış düzenlenemez.", "code": "not_editable"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for field in ("name", "description", "trigger_type", "priority", "canvas_meta"):
            if field in request.data:
                setattr(wf, field, request.data[field])
        wf.save()
        return Response(WorkflowDetailSerializer(wf).data)


class WorkflowGraphReplaceView(TenantQuerysetMixin, generics.GenericAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK
    queryset = CollectionWorkflow.objects.all()

    def put(self, request, *args, **kwargs):
        wf = self.get_object()
        serializer = WorkflowGraphSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            replace_workflow_graph(
                wf,
                steps=serializer.validated_data["steps"],
                edges=serializer.validated_data.get("edges") or [],
                canvas_meta=serializer.validated_data.get("canvas_meta"),
            )
        except WorkflowServiceError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        wf.refresh_from_db()
        return Response(WorkflowDetailSerializer(wf).data)


class WorkflowActivateView(TenantQuerysetMixin, generics.GenericAPIView):
    """NP-216 — publish draft (creates new version family)."""

    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK
    queryset = CollectionWorkflow.objects.all()

    def post(self, request, *args, **kwargs):
        wf = self.get_object()
        try:
            result = publish_workflow(wf, actor=request.user)
        except WorkflowServiceError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "published": WorkflowDetailSerializer(result["published"]).data,
                "draft": WorkflowDetailSerializer(result["draft"]).data,
            }
        )


class WorkflowDeactivateView(TenantQuerysetMixin, generics.GenericAPIView):
    """NP-216 — archive workflow."""

    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK
    queryset = CollectionWorkflow.objects.all()

    def post(self, request, *args, **kwargs):
        wf = archive_workflow(self.get_object())
        return Response(CollectionWorkflowSerializer(wf).data)


class WorkflowPublishView(WorkflowActivateView):
    """Alias for activate → publish."""


class WorkflowArchiveView(WorkflowDeactivateView):
    """Alias for deactivate → archive."""


class WorkflowVersionsView(TenantQuerysetMixin, generics.GenericAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK
    queryset = CollectionWorkflow.objects.all()

    def get(self, request, *args, **kwargs):
        wf = self.get_object()
        versions = list_family_versions(wf)
        return Response(CollectionWorkflowSerializer(versions, many=True).data)


class WorkflowSimulateView(TenantQuerysetMixin, generics.GenericAPIView):
    """NP-215 — dry-run against last N days of org data."""

    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK
    queryset = CollectionWorkflow.objects.all()

    def post(self, request, *args, **kwargs):
        wf = self.get_object()
        serializer = WorkflowSimulateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data.get("days") or 30
        result = simulate_workflow(wf, days=days)
        return Response(result)


class WorkflowTestRunView(TenantQuerysetMixin, generics.GenericAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK
    queryset = CollectionWorkflow.objects.all()

    def post(self, request, *args, **kwargs):
        wf = self.get_object()
        serializer = WorkflowTestRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = self.get_current_organization()
        data = serializer.validated_data
        customer = Customer.objects.filter(
            pk=data["customer_id"], organization=org
        ).first()
        if customer is None:
            return Response({"detail": "Müşteri bulunamadı."}, status=400)

        invoice = None
        promise = None
        if data.get("invoice_id"):
            from apps.invoices.models import Invoice

            invoice = Invoice.objects.filter(
                pk=data["invoice_id"], organization=org, customer=customer
            ).first()
        if data.get("promise_id"):
            from apps.collections.models import PaymentPromise

            promise = PaymentPromise.objects.filter(
                pk=data["promise_id"], organization=org, customer=customer
            ).first()

        key = data.get("idempotency_key") or f"test:{wf.id}:{customer.id}:{timezone.now().timestamp()}"
        execution = run_workflow(
            wf,
            customer=customer,
            context=data.get("context") or {},
            idempotency_key=key,
            trigger_entity_type="manual",
            trigger_entity_id=str(customer.id),
            invoice=invoice,
            promise=promise,
        )
        return Response(WorkflowExecutionSerializer(execution).data)


class WorkflowExecutionListView(TenantQuerysetMixin, generics.ListAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK
    pagination_class = StandardResultsSetPagination
    serializer_class = WorkflowExecutionSerializer

    def get_queryset(self):
        wf_id = self.kwargs["pk"]
        return WorkflowExecution.objects.filter(
            organization=self.get_current_organization(),
            workflow_id=wf_id,
        )


class WorkflowApprovalDecideView(TenantQuerysetMixin, generics.GenericAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK
    queryset = WorkflowApprovalRequest.objects.select_related("execution", "step").all()

    def post(self, request, *args, **kwargs):
        approval = self.get_object()
        serializer = WorkflowApprovalDecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if approval.status != WorkflowApprovalStatus.PENDING:
            return Response({"detail": "Onay zaten sonuçlanmış."}, status=400)

        decision = serializer.validated_data["decision"]
        approval.status = (
            WorkflowApprovalStatus.APPROVED
            if decision == "approved"
            else WorkflowApprovalStatus.REJECTED
        )
        approval.decided_by = request.user
        approval.decided_at = timezone.now()
        approval.decision_note = serializer.validated_data.get("note") or ""
        approval.save()

        WorkflowExecutionLog.objects.create(
            organization=approval.organization,
            execution=approval.execution,
            step=approval.step,
            event=WorkflowLogEvent.APPROVAL_DECIDED,
            message=decision,
            payload={"approval_id": approval.id, "decision": decision},
        )

        if decision == "approved":
            resume_execution(approval.execution)
        else:
            execution = approval.execution
            execution.status = "failed"
            execution.error_message = "approval_rejected"
            execution.completed_at = timezone.now()
            execution.save(
                update_fields=["status", "error_message", "completed_at", "updated_at"]
            )

        return Response(WorkflowApprovalSerializer(approval).data)


class OrganizationHolidayListCreateView(APIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK

    def get_org(self, request):
        from apps.organizations.tenancy import get_request_organization
        from rest_framework.exceptions import PermissionDenied

        org = get_request_organization(request)
        if org is None:
            raise PermissionDenied(detail="Organization context is required.")
        return org

    def get(self, request, *args, **kwargs):
        org = self.get_org(request)
        rows = OrganizationHoliday.objects.filter(organization=org).order_by("date")
        data = [
            {"id": h.id, "date": h.date.isoformat(), "name": h.name}
            for h in rows
        ]
        return Response(data)

    def post(self, request, *args, **kwargs):
        org = self.get_org(request)
        serializer = OrganizationHolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        holiday, _ = OrganizationHoliday.objects.update_or_create(
            organization=org,
            date=serializer.validated_data["date"],
            defaults={"name": serializer.validated_data.get("name") or ""},
        )
        return Response(
            {"id": holiday.id, "date": holiday.date.isoformat(), "name": holiday.name},
            status=status.HTTP_201_CREATED,
        )


class OrganizationHolidayDetailView(APIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_COLLECTION_TASK

    def delete(self, request, pk, *args, **kwargs):
        from apps.organizations.tenancy import get_request_organization
        from rest_framework.exceptions import PermissionDenied

        org = get_request_organization(request)
        if org is None:
            raise PermissionDenied(detail="Organization context is required.")
        deleted, _ = OrganizationHoliday.objects.filter(organization=org, pk=pk).delete()
        if not deleted:
            return Response({"detail": "Not found."}, status=404)
        return Response(status=status.HTTP_204_NO_CONTENT)
