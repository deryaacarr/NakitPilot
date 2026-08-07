from rest_framework import serializers

from apps.reports.models import ExportJob, ReportType


class ExportJobSerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()
    report_type_label = serializers.SerializerMethodField()

    class Meta:
        model = ExportJob
        fields = (
            "id",
            "report_type",
            "report_type_label",
            "status",
            "status_label",
            "filters",
            "original_filename",
            "file_size",
            "row_count",
            "error_message",
            "expires_at",
            "created_at",
            "updated_at",
            "completed_at",
            "requested_by",
        )
        read_only_fields = fields

    def get_status_label(self, obj: ExportJob) -> str:
        return obj.get_status_display()

    def get_report_type_label(self, obj: ExportJob) -> str:
        return obj.get_report_type_display()


class ExportCreateSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=ReportType.choices)
    filters = serializers.DictField(required=False, default=dict)
