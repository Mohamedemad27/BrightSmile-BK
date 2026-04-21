from rest_framework import serializers

from apps.users.models import Doctor

from apps.users.models import Patient

from .models import Appointment, DoctorReview, DoctorService, FavoriteDoctor, HealthTip, MedicalHistory, Notification, ServiceCategory


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ['id', 'name', 'icon_name']


class HealthTipSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthTip
        fields = ['id', 'title', 'content']


class MedicalHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalHistory
        fields = [
            'id', 'diabetes', 'heart_disease', 'blood_pressure',
            'allergies', 'bleeding_disorders', 'asthma', 'pregnancy',
            'smoking', 'previous_dental_surgery', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FavoriteDoctorSerializer(serializers.ModelSerializer):
    doctor_id = serializers.UUIDField(source='doctor.user.id')
    name = serializers.CharField(source='doctor.full_name')
    rating = serializers.DecimalField(source='doctor.rating', max_digits=3, decimal_places=1)
    profile_image_url = serializers.CharField(source='doctor.profile_image_url')

    class Meta:
        model = FavoriteDoctor
        fields = ['id', 'doctor_id', 'name', 'rating', 'profile_image_url', 'created_at']


class TopDoctorSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source='user.id')
    name = serializers.CharField(source='user.get_full_name')
    profile_image_url = serializers.CharField()
    rating = serializers.DecimalField(max_digits=3, decimal_places=1)
    categories = ServiceCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Doctor
        fields = ['id', 'name', 'rating', 'profile_image_url', 'categories']


class DoctorServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorService
        fields = ['id', 'name', 'price']


class DoctorReviewSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(read_only=True)

    class Meta:
        model = DoctorReview
        fields = ['id', 'patient_name', 'rating', 'comment', 'created_at']


class FeaturedReviewSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(read_only=True)
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)

    class Meta:
        model = DoctorReview
        fields = ['id', 'patient_name', 'doctor_name', 'rating', 'comment', 'created_at']


class DoctorDetailSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source='user.id')
    name = serializers.CharField(source='user.get_full_name')
    email = serializers.EmailField(source='user.email')
    profile_image_url = serializers.CharField()
    rating = serializers.DecimalField(max_digits=3, decimal_places=1)
    total_reviews = serializers.IntegerField()
    bio = serializers.CharField()
    location = serializers.CharField()
    working_hours = serializers.CharField()
    categories = ServiceCategorySerializer(many=True, read_only=True)
    services = DoctorServiceSerializer(many=True, read_only=True)
    reviews = DoctorReviewSerializer(many=True, read_only=True)

    phone_number = serializers.CharField()
    facebook_url = serializers.CharField()
    instagram_url = serializers.CharField()
    twitter_url = serializers.CharField()
    linkedin_url = serializers.CharField()

    class Meta:
        model = Doctor
        fields = [
            'id', 'name', 'email', 'profile_image_url', 'rating',
            'total_reviews', 'bio', 'location', 'working_hours',
            'phone_number', 'facebook_url', 'instagram_url',
            'twitter_url', 'linkedin_url',
            'categories', 'services', 'reviews',
        ]


# ─── Appointment Serializers ───


class AppointmentCreateSerializer(serializers.Serializer):
    doctor_id = serializers.UUIDField()
    service_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    date = serializers.DateField()
    time_slot = serializers.CharField(max_length=20)
    notes = serializers.CharField(max_length=500, required=False, default='')

    def validate_doctor_id(self, value):
        try:
            Doctor.objects.get(user__id=value, user__is_active=True)
        except Doctor.DoesNotExist:
            raise serializers.ValidationError('Doctor not found.')
        return value

    def validate_service_ids(self, value):
        found = DoctorService.objects.filter(id__in=value).count()
        if found != len(value):
            raise serializers.ValidationError('One or more services not found.')
        return value


class AppointmentServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorService
        fields = ['id', 'name', 'price']


class AppointmentListSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.full_name')
    doctor_image = serializers.CharField(source='doctor.profile_image_url')
    doctor_id = serializers.UUIDField(source='doctor.user_id')
    patient_name = serializers.CharField(source='patient.get_full_name')
    services = AppointmentServiceSerializer(many=True, read_only=True)
    has_review = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id', 'doctor_id', 'doctor_name', 'doctor_image', 'patient_name',
            'date', 'time_slot', 'status', 'total_price', 'services',
            'has_review', 'notes', 'created_at',
        ]

    def get_has_review(self, obj):
        return hasattr(obj, 'review') and obj.review is not None


class AppointmentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['confirmed', 'rejected', 'completed', 'cancelled'],
    )


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=500)


# ─── Notification Serializers ───


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'notif_type', 'is_read', 'created_at']


# ─── Profile Serializers ───


class ProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    user_type = serializers.CharField(read_only=True)
    phone_number = serializers.CharField(max_length=20, required=False)
    date_of_birth = serializers.DateField(required=False)
    is_verified = serializers.BooleanField(read_only=True)
    push_notifications = serializers.BooleanField(required=False, default=True)
    email_notifications = serializers.BooleanField(required=False, default=True)


# ─── Health Check Serializers ───


class ServiceStatusSerializer(serializers.Serializer):
    service = serializers.CharField(help_text="Name of the service")
    status = serializers.CharField(help_text="Status of the service (healthy/unhealthy)")
    response_time = serializers.FloatField(help_text="Response time in milliseconds", allow_null=True)
    details = serializers.CharField(help_text="Additional details about the service", allow_null=True)


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.CharField(help_text="Overall system status")
    timestamp = serializers.DateTimeField(help_text="Timestamp of the health check")
    services = ServiceStatusSerializer(many=True, help_text="Status of individual services")
    version = serializers.CharField(help_text="Application version")
    environment = serializers.CharField(help_text="Current environment (dev/prod)")
