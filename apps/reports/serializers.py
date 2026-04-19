from rest_framework import serializers


class ReportQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=200)

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError({"date_to": "date_to must be greater than or equal to date_from."})
        return attrs


class ReportExportRequestSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(
        choices=[
            "admin_appointments",
            "admin_audit",
            "admin_doctors",
            "admin_patients",
            "doctor_appointments",
            "doctor_patients",
            "patient_report",
        ]
    )
    file_format = serializers.ChoiceField(choices=["csv", "xlsx", "pdf"], default="csv")
    filters = serializers.DictField(required=False, default=dict)


class ReportTaskStatusSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    status = serializers.CharField()
    download_url = serializers.CharField(allow_null=True, required=False)
    error = serializers.CharField(allow_null=True, required=False)
