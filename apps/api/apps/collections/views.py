from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.collections.models import CollectionTask
from apps.collections.serializers import (
    AcceptPaymentPlanSerializer,
    BulkAssignSerializer,
    CancelTaskSerializer,
    CollectionTaskCreateSerializer,
    CollectionTaskSerializer,
    CollectionTaskUpdateSerializer,
    CompleteTaskSerializer,
    ConfirmStructuredNotesSerializer,
    ParseNotesSerializer,
)
from apps.collections.services import customer_timeline, today_board
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CollectionTaskListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    """GET/POST /api/collection-tasks/ — NP-080."""

    queryset = CollectionTask.objects.select_related(
        "customer", "assigned_to", "created_by", "invoice", "related_promise"
    )
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CollectionTaskCreateSerializer
        return CollectionTaskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if customer := params.get("customer", "").strip():
            qs = qs.filter(customer_id=customer)
        if status_value := params.get("status", "").strip():
            qs = qs.filter(status=status_value)
        if assigned := params.get("assigned_to", "").strip():
            qs = qs.filter(assigned_to_id=assigned)
        if due_from := params.get("due_date_from", "").strip():
            qs = qs.filter(due_date__gte=due_from)
        if due_to := params.get("due_date_to", "").strip():
            qs = qs.filter(due_date__lte=due_to)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["organization"] = self.get_current_organization()
        return ctx

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        data = CollectionTaskSerializer(task, context=self.get_serializer_context()).data
        warning = getattr(task, "_assign_warning", None)
        body = {"task": data}
        if warning:
            body["warning"] = warning
            body["warning_message"] = (
                "Atanan kullanıcı pasif. Lütfen aktif bir sorumlu seçin."
            )
        return Response(body if warning else data, status=status.HTTP_201_CREATED)


class CollectionTaskDetailView(TenantQuerysetMixin, generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/collection-tasks/{id}/ — NP-080."""

    queryset = CollectionTask.objects.select_related(
        "customer", "assigned_to", "created_by", "invoice", "related_promise"
    )
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return CollectionTaskUpdateSerializer
        return CollectionTaskSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        data = CollectionTaskSerializer(task).data
        warning = serializer.context.get("assign_warning")
        if warning:
            return Response(
                {
                    "task": data,
                    "warning": warning,
                    "warning_message": (
                        "Atanan kullanıcı pasif. Lütfen aktif bir sorumlu seçin."
                    ),
                }
            )
        return Response(data)


class CollectionTaskCompleteView(TenantQuerysetMixin, APIView):
    """POST /api/collection-tasks/{id}/complete/ — NP-083."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_COLLECTION_TASK
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        try:
            task = CollectionTask.objects.for_organization(
                self.get_current_organization()
            ).get(pk=pk)
        except CollectionTask.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ser = CompleteTaskSerializer(
            data=request.data, context={"request": request, "task": task}
        )
        ser.is_valid(raise_exception=True)
        result = ser.save()
        return Response(
            {
                "task": CollectionTaskSerializer(result["task"]).data,
                "follow_up": CollectionTaskSerializer(result["follow_up"]).data
                if result["follow_up"]
                else None,
                "promise_id": result["promise"].id if result["promise"] else None,
            }
        )


class CollectionTaskCancelView(TenantQuerysetMixin, APIView):
    """POST /api/collection-tasks/{id}/cancel/ — NP-080."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_COLLECTION_TASK
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        try:
            task = CollectionTask.objects.for_organization(
                self.get_current_organization()
            ).get(pk=pk)
        except CollectionTask.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ser = CancelTaskSerializer(
            data=request.data or {}, context={"request": request, "task": task}
        )
        ser.is_valid(raise_exception=True)
        task = ser.save()
        return Response(CollectionTaskSerializer(task).data)


class CollectionTaskTodayBoardView(TenantQuerysetMixin, APIView):
    """GET /api/collection-tasks/today/ — NP-081."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request):
        board = today_board(organization=self.get_current_organization())
        return Response(
            {
                "overdue": CollectionTaskSerializer(board["overdue"], many=True).data,
                "today": CollectionTaskSerializer(board["today"], many=True).data,
                "upcoming": CollectionTaskSerializer(board["upcoming"], many=True).data,
                "completed": CollectionTaskSerializer(board["completed"], many=True).data,
            }
        )


class CollectionTaskBulkAssignView(TenantQuerysetMixin, APIView):
    """POST /api/collection-tasks/bulk-assign/ — NP-085."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_COLLECTION_TASK
    read_permission = Permission.VIEW_REPORTS

    def post(self, request):
        ser = BulkAssignSerializer(
            data=request.data,
            context={
                "request": request,
                "organization": self.get_current_organization(),
            },
        )
        ser.is_valid(raise_exception=True)
        result = ser.save()
        body = {
            "updated": result["updated"],
            "assigned_to": result["assigned_to"],
        }
        if result.get("warning"):
            body["warning"] = result["warning"]
            body["warning_message"] = (
                "Atanan kullanıcı pasif. Lütfen aktif bir sorumlu seçin."
            )
        return Response(body)


class CollectionTaskPrepareCallView(TenantQuerysetMixin, APIView):
    """GET /api/collection-tasks/{id}/prepare-call/ — NP-231."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request, pk: int):
        from apps.collections.call_prep import build_call_preparation

        try:
            task = (
                CollectionTask.objects.for_organization(self.get_current_organization())
                .select_related("customer", "organization")
                .get(pk=pk)
            )
        except CollectionTask.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        payload = build_call_preparation(
            task.customer,
            organization=self.get_current_organization(),
            task=task,
        )
        return Response(payload)


class CollectionTaskParseNotesView(TenantQuerysetMixin, APIView):
    """POST /api/collection-tasks/{id}/parse-notes/ — NP-232 draft only."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_COLLECTION_TASK
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        try:
            CollectionTask.objects.for_organization(
                self.get_current_organization()
            ).get(pk=pk)
        except CollectionTask.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ser = ParseNotesSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(ser.save())


class CollectionTaskConfirmNotesView(TenantQuerysetMixin, APIView):
    """POST /api/collection-tasks/{id}/confirm-notes/ — NP-232 persist after confirm."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_COLLECTION_TASK
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        try:
            task = CollectionTask.objects.for_organization(
                self.get_current_organization()
            ).get(pk=pk)
        except CollectionTask.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ser = ConfirmStructuredNotesSerializer(
            data=request.data, context={"request": request, "task": task}
        )
        ser.is_valid(raise_exception=True)
        result = ser.save()
        return Response(
            {
                "activity_id": result["activity_id"],
                "promise_id": result["promise"].id if result["promise"] else None,
                "follow_up": CollectionTaskSerializer(result["follow_up"]).data
                if result["follow_up"]
                else None,
                "structured": result["structured"],
                "completed": result["completed"],
                "task": CollectionTaskSerializer(result["task"]).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CustomerTimelineView(APIView):
    """GET /api/customers/{id}/timeline/ — NP-086."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        from apps.customers.models import Customer

        if not Customer.objects.for_organization(organization).filter(pk=pk).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        events = customer_timeline(organization=organization, customer_id=pk)
        return Response({"results": events})


class CustomerPaymentPlanSuggestView(APIView):
    """GET /api/customers/{id}/payment-plan-suggestions/ — NP-234 (non-binding)."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request, pk: int):
        from apps.ai_usage.models import AIFeature
        from apps.ai_usage.services import AIUsageLimitExceeded, run_metered
        from apps.collections.payment_plans import suggest_payment_plans
        from apps.customers.models import Customer

        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        customer = (
            Customer.objects.for_organization(organization).filter(pk=pk).first()
        )
        if customer is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        def _produce(_text: str):
            from apps.ai_usage.prompt_security import (
                PAYMENT_PLAN_SCHEMA,
                PromptSecurityError,
                secure_ai_produce,
            )

            try:
                return secure_ai_produce(
                    organization=organization,
                    scoped_objects=[customer],
                    output_schema=PAYMENT_PLAN_SCHEMA,
                    producer=lambda: suggest_payment_plans(
                        customer, organization=organization
                    ),
                )
            except PromptSecurityError as exc:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"detail": exc.message, "code": exc.code}) from exc

        try:
            metered = run_metered(
                organization=organization,
                user=request.user,
                feature=AIFeature.PAYMENT_PLAN,
                model="deterministic",
                input_text=f"customer={pk}",
                cache_payload={"customer_id": pk, "feature": "payment_plan"},
                producer=_produce,
            )
        except AIUsageLimitExceeded as exc:
            return Response(
                {"detail": exc.message, "code": exc.code, **exc.details},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return Response(metered["result"])


class CustomerPaymentPlanAcceptView(APIView):
    """POST /api/customers/{id}/payment-plan-suggestions/accept/ — NP-234."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def post(self, request, pk: int):
        from apps.collections.payment_plans import PaymentPlanError, accept_payment_plan
        from apps.customers.models import Customer

        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        customer = (
            Customer.objects.for_organization(organization).filter(pk=pk).first()
        )
        if customer is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ser = AcceptPaymentPlanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            result = accept_payment_plan(
                customer,
                organization=organization,
                option_id=ser.validated_data["option_id"],
                confirmed=bool(ser.validated_data["confirmed"]),
                actor=request.user,
            )
        except PaymentPlanError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result, status=status.HTTP_201_CREATED)


class CollectionTaskOfflineSyncView(APIView):
    """POST /api/collection-tasks/offline-sync/ — NP-342."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def post(self, request):
        from apps.collections.offline_sync import sync_offline_batch

        organization = get_request_organization(request)
        items = request.data.get("items") or []
        if not isinstance(items, list):
            return Response(
                {"detail": "items bir dizi olmalı."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = sync_offline_batch(
            organization=organization,
            user=request.user,
            items=items,
        )
        return Response(result)
