from rest_framework import serializers

from apps.imports.models import DuplicatePolicy, ImportError, ImportJob
from apps.imports.schema import CANONICAL_COLUMNS, FIELD_LABELS, REQUIRED_FIELDS


class ImportJobSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.EmailField(source="uploaded_by.email", read_only=True)

    class Meta:
        model = ImportJob
        fields = (
            "id",
            "organization",
            "import_type",
            "status",
            "duplicate_policy",
            "original_filename",
            "content_type",
            "file_size",
            "file_hash",
            "headers",
            "column_mapping",
            "preview_summary",
            "preview_errors",
            "result_summary",
            "total_rows",
            "valid_rows",
            "invalid_rows",
            "successful_rows",
            "failed_rows",
            "skipped_duplicates",
            "celery_task_id",
            "uploaded_by",
            "uploaded_by_email",
            "error_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ColumnMappingSerializer(serializers.Serializer):
    column_mapping = serializers.DictField(
        child=serializers.CharField(allow_blank=True, allow_null=True, required=False),
    )

    def validate_column_mapping(self, value: dict):
        cleaned: dict[str, str | None] = {}
        for field in CANONICAL_COLUMNS:
            raw = value.get(field)
            if raw in (None, ""):
                cleaned[field] = None
            else:
                cleaned[field] = str(raw).strip()
        unknown = set(value.keys()) - set(CANONICAL_COLUMNS)
        if unknown:
            raise serializers.ValidationError(f"Bilinmeyen alanlar: {', '.join(sorted(unknown))}")
        return cleaned


class CommitImportSerializer(serializers.Serializer):
    duplicate_policy = serializers.ChoiceField(
        choices=DuplicatePolicy.choices,
        required=False,
        default=DuplicatePolicy.SKIP,
    )


class ImportErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportError
        fields = (
            "id",
            "row_number",
            "field_name",
            "raw_value",
            "error_message",
            "kind",
            "created_at",
        )


class CanonicalFieldsSerializer(serializers.Serializer):
    fields = serializers.SerializerMethodField()

    def get_fields(self, _obj):
        return [
            {
                "key": key,
                "label": FIELD_LABELS[key],
                "required": key in REQUIRED_FIELDS,
            }
            for key in CANONICAL_COLUMNS
        ]
