from rest_framework import serializers


class ServiceStatusSerializer(serializers.Serializer):
    """Serializer for individual service status."""
    service = serializers.CharField(help_text="Name of the service")
    status = serializers.CharField(help_text="Status of the service (healthy/unhealthy)")
    response_time = serializers.FloatField(help_text="Response time in milliseconds", allow_null=True)
    details = serializers.CharField(help_text="Additional details about the service", allow_null=True)


class HealthCheckSerializer(serializers.Serializer):
    """Serializer for overall health check response."""
    status = serializers.CharField(help_text="Overall system status (healthy/degraded/unhealthy)")
    timestamp = serializers.DateTimeField(help_text="Timestamp of the health check")
    services = ServiceStatusSerializer(many=True, help_text="Status of individual services")
    version = serializers.CharField(help_text="Application version")
    environment = serializers.CharField(help_text="Current environment (dev/prod)")
