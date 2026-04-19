from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.models import (
    Appointment,
    DoctorReview,
    DoctorService,
    HealthTip,
    ServiceCategory,
)
from apps.dashboard.models import AuditLog
from apps.users.models import (
    AdminRole,
    AdminRoleAssignment,
    Doctor,
    Patient,
    Secretary,
)
from utils.validators import phone_number_validator

User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════
# Dashboard Me
# ═══════════════════════════════════════════════════════════════════════


class DashboardMeSerializer(serializers.ModelSerializer):
    """
    Returns the authenticated user's info along with resolved permissions
    and (for secretaries) the assigned doctor.
    """

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    permissions = serializers.SerializerMethodField()
    assigned_doctor = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'user_type',
            'is_active',
            'is_verified',
            'is_2fa_enabled',
            'auth_provider',
            'push_notifications',
            'email_notifications',
            'created_at',
            'permissions',
            'assigned_doctor',
        ]
        read_only_fields = fields

    def get_permissions(self, obj):
        """
        Resolve the flat list of permission codenames.
        - admin  -> permissions from AdminRoleAssignment.role.permissions
        - doctor / secretary -> permissions from User.groups (Django groups)
        """
        if obj.user_type == 'admin':
            try:
                assignment = obj.admin_role_assignment
                return list(
                    assignment.role.permissions
                    .values_list('codename', flat=True)
                )
            except AdminRoleAssignment.DoesNotExist:
                return []
        # doctors / secretaries fall back to group permissions
        return list(
            obj.get_group_permissions()
        )

    def get_assigned_doctor(self, obj):
        """Return the doctor info for secretary users, None otherwise."""
        if obj.user_type != 'secretary':
            return None
        try:
            secretary = obj.secretary_profile
            doctor = secretary.doctor
            return {
                'id': str(doctor.user_id),
                'name': doctor.full_name,
                'specialty': doctor.specialty,
                'profile_image_url': doctor.profile_image_url,
            }
        except Secretary.DoesNotExist:
            return None


# ═══════════════════════════════════════════════════════════════════════
# Admin – Users
# ═══════════════════════════════════════════════════════════════════════


class AdminUserListSerializer(serializers.ModelSerializer):
    """Compact user representation for admin list views."""

    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'user_type',
            'is_active',
            'is_verified',
            'created_at',
        ]
        read_only_fields = fields


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """
    Full user detail for admin view, including type-specific profile info.
    """

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'user_type',
            'is_active',
            'is_verified',
            'is_2fa_enabled',
            'auth_provider',
            'push_notifications',
            'email_notifications',
            'last_login',
            'created_at',
            'profile',
            'role',
        ]
        read_only_fields = fields

    def get_profile(self, obj):
        """Return the type-specific profile payload."""
        if obj.user_type == 'patient':
            try:
                p = obj.patient_profile
                return {
                    'phone_number': p.phone_number,
                    'date_of_birth': str(p.date_of_birth),
                    'age': p.age,
                }
            except Patient.DoesNotExist:
                return None
        if obj.user_type == 'doctor':
            try:
                d = obj.doctor_profile
                return {
                    'phone_number': d.phone_number,
                    'specialty': d.specialty,
                    'rating': str(d.rating),
                    'total_reviews': d.total_reviews,
                    'profile_image_url': d.profile_image_url,
                    'bio': d.bio,
                    'location': d.location,
                    'working_hours': d.working_hours,
                }
            except Doctor.DoesNotExist:
                return None
        if obj.user_type == 'secretary':
            try:
                s = obj.secretary_profile
                return {
                    'phone_number': s.phone_number,
                    'doctor_id': str(s.doctor.user_id),
                    'doctor_name': s.doctor.full_name,
                    'is_active': s.is_active,
                }
            except Secretary.DoesNotExist:
                return None
        return None

    def get_role(self, obj):
        """Return the admin role assignment if present."""
        if obj.user_type != 'admin':
            return None
        try:
            assignment = obj.admin_role_assignment
            return {
                'id': str(assignment.role.id),
                'name': assignment.role.name,
            }
        except AdminRoleAssignment.DoesNotExist:
            return None


class AdminUserUpdateSerializer(serializers.Serializer):
    """Allow admins to patch user flags."""

    is_active = serializers.BooleanField(required=True)


# ═══════════════════════════════════════════════════════════════════════
# Admin – Doctors
# ═══════════════════════════════════════════════════════════════════════


class AdminDoctorListSerializer(serializers.ModelSerializer):
    """Doctor list for admin panel."""

    id = serializers.UUIDField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = Doctor
        fields = [
            'id',
            'email',
            'full_name',
            'specialty',
            'rating',
            'total_reviews',
            'is_active',
            'profile_image_url',
            'location',
            'created_at',
        ]
        read_only_fields = fields


class AdminDoctorProfileUpdateSerializer(serializers.ModelSerializer):
    """Admin-only patch serializer for doctor profile data."""

    class Meta:
        model = Doctor
        fields = [
            'phone_number',
            'specialty',
            'profile_image_url',
            'bio',
            'location',
            'working_hours',
            'facebook_url',
            'instagram_url',
            'twitter_url',
            'linkedin_url',
            'categories',
        ]


class AdminAuditEntrySerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', allow_null=True, read_only=True)
    user_name = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user_email',
            'user_name',
            'action',
            'action_display',
            'target_type',
            'target_id',
            'description',
            'ip_address',
            'metadata',
            'created_at',
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        if not obj.user:
            return 'System'
        first = obj.user.first_name or ''
        last = obj.user.last_name or ''
        return f'{first} {last}'.strip() or obj.user.email

    def get_action_display(self, obj):
        return (obj.action or '').replace('_', ' ').title()


class SyndicateDoctorPayloadSerializer(serializers.Serializer):
    email = serializers.EmailField()
    license_status = serializers.CharField(required=False, allow_blank=True)
    specialty = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)

# ═══════════════════════════════════════════════════════════════════════
# Admin – Appointments
# ═══════════════════════════════════════════════════════════════════════


class AdminAppointmentServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorService
        fields = ['id', 'name', 'price']


class AdminAppointmentListSerializer(serializers.ModelSerializer):
    """Appointment list for the admin panel."""

    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    patient_email = serializers.EmailField(source='patient.email', read_only=True)
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)
    doctor_id = serializers.UUIDField(source='doctor.user_id', read_only=True)
    services = AdminAppointmentServiceSerializer(many=True, read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_name',
            'patient_email',
            'doctor_id',
            'doctor_name',
            'date',
            'time_slot',
            'status',
            'total_price',
            'notes',
            'services',
            'created_at',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════════════
# Admin – Reviews
# ═══════════════════════════════════════════════════════════════════════


class AdminReviewListSerializer(serializers.ModelSerializer):
    """Review list for the admin panel."""

    patient_name = serializers.CharField(source='user.get_full_name', read_only=True)
    patient_email = serializers.EmailField(source='user.email', read_only=True)
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)
    doctor_id = serializers.UUIDField(source='doctor.user_id', read_only=True)

    class Meta:
        model = DoctorReview
        fields = [
            'id',
            'patient_name',
            'patient_email',
            'doctor_id',
            'doctor_name',
            'rating',
            'comment',
            'created_at',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════════════
# Admin – Categories & Health Tips
# ═══════════════════════════════════════════════════════════════════════


class AdminCategorySerializer(serializers.ModelSerializer):
    """ServiceCategory CRUD for admin panel."""

    class Meta:
        model = ServiceCategory
        fields = ['id', 'name', 'icon_name', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class AdminHealthTipSerializer(serializers.ModelSerializer):
    """HealthTip CRUD for admin panel."""

    class Meta:
        model = HealthTip
        fields = ['id', 'title', 'content', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# ═══════════════════════════════════════════════════════════════════════
# Admin – Analytics
# ═══════════════════════════════════════════════════════════════════════


class AdminAnalyticsSerializer(serializers.Serializer):
    """Platform-wide analytics / stats for the admin dashboard."""

    total_users = serializers.IntegerField()
    total_patients = serializers.IntegerField()
    total_doctors = serializers.IntegerField()
    total_appointments = serializers.IntegerField()
    pending_appointments = serializers.IntegerField()
    completed_appointments = serializers.IntegerField()
    cancelled_appointments = serializers.IntegerField()
    total_reviews = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    new_users_this_month = serializers.IntegerField()
    appointments_this_month = serializers.IntegerField()


# ═══════════════════════════════════════════════════════════════════════
# Admin – Roles
# ═══════════════════════════════════════════════════════════════════════


class AdminRoleSerializer(serializers.ModelSerializer):
    """AdminRole CRUD.  Permissions are exposed as a list of codenames."""

    permissions = serializers.SlugRelatedField(
        many=True,
        slug_field='codename',
        queryset=__import__('django.contrib.auth.models', fromlist=['Permission']).Permission.objects.all(),
    )

    class Meta:
        model = AdminRole
        fields = ['id', 'name', 'description', 'permissions', 'is_system', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_system', 'created_at', 'updated_at']


class AdminRoleAssignSerializer(serializers.Serializer):
    """Assign (or reassign) a user to an admin role."""

    user_id = serializers.UUIDField()
    role_id = serializers.UUIDField()

    def validate_user_id(self, value):
        try:
            user = User.objects.get(id=value, user_type='admin')
        except User.DoesNotExist:
            raise serializers.ValidationError('Admin user not found.')
        return value

    def validate_role_id(self, value):
        try:
            AdminRole.objects.get(id=value)
        except AdminRole.DoesNotExist:
            raise serializers.ValidationError('Role not found.')
        return value

    def create(self, validated_data):
        assignment, _ = AdminRoleAssignment.objects.update_or_create(
            user_id=validated_data['user_id'],
            defaults={'role_id': validated_data['role_id']},
        )
        return assignment


# ═══════════════════════════════════════════════════════════════════════
# Doctor – Profile
# ═══════════════════════════════════════════════════════════════════════


class DoctorProfileSerializer(serializers.ModelSerializer):
    """
    Doctor's own profile — read + update.
    Nested user fields (first_name, last_name, email) are read-only here;
    editable doctor-specific fields live on the Doctor model.
    """

    id = serializers.UUIDField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    categories = serializers.SlugRelatedField(
        many=True,
        slug_field='id',
        queryset=ServiceCategory.objects.filter(is_active=True),
        required=False,
    )

    class Meta:
        model = Doctor
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'phone_number',
            'specialty',
            'rating',
            'total_reviews',
            'profile_image_url',
            'bio',
            'location',
            'working_hours',
            'facebook_url',
            'instagram_url',
            'twitter_url',
            'linkedin_url',
            'categories',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'rating',
            'total_reviews',
            'created_at',
        ]


# ═══════════════════════════════════════════════════════════════════════
# Doctor – Appointments
# ═══════════════════════════════════════════════════════════════════════


class DoctorAppointmentServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorService
        fields = ['id', 'name', 'price']


class DoctorAppointmentSerializer(serializers.ModelSerializer):
    """Appointments visible to the doctor."""

    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    patient_email = serializers.EmailField(source='patient.email', read_only=True)
    patient_id = serializers.UUIDField(source='patient.id', read_only=True)
    services = DoctorAppointmentServiceSerializer(many=True, read_only=True)
    has_review = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_id',
            'patient_name',
            'patient_email',
            'date',
            'time_slot',
            'status',
            'total_price',
            'notes',
            'services',
            'has_review',
            'created_at',
        ]
        read_only_fields = fields

    def get_has_review(self, obj):
        return hasattr(obj, 'review') and obj.review is not None


# ═══════════════════════════════════════════════════════════════════════
# Doctor – Patients
# ═══════════════════════════════════════════════════════════════════════


class DoctorPatientSerializer(serializers.ModelSerializer):
    """Unique patients who have booked with the doctor."""

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    date_of_birth = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    total_appointments = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'date_of_birth',
            'phone_number',
            'total_appointments',
        ]
        read_only_fields = fields

    def get_date_of_birth(self, obj):
        try:
            return str(obj.patient_profile.date_of_birth)
        except Patient.DoesNotExist:
            return None

    def get_phone_number(self, obj):
        try:
            return obj.patient_profile.phone_number
        except Patient.DoesNotExist:
            return None


# ═══════════════════════════════════════════════════════════════════════
# Doctor – Services
# ═══════════════════════════════════════════════════════════════════════


class DoctorServiceSerializer(serializers.ModelSerializer):
    """CRUD serializer for a doctor's own services."""

    class Meta:
        model = DoctorService
        fields = ['id', 'name', 'price']
        read_only_fields = ['id']

    def create(self, validated_data):
        # The view is responsible for injecting `doctor` into validated_data
        return super().create(validated_data)

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError('Service name is required.')
        return name

    def validate_price(self, value):
        if value is None:
            raise serializers.ValidationError('Price is required.')
        if value <= 0:
            raise serializers.ValidationError('Price must be greater than 0.')
        return value


# ═══════════════════════════════════════════════════════════════════════
# Doctor – Secretaries
# ═══════════════════════════════════════════════════════════════════════


class DoctorSecretaryListSerializer(serializers.ModelSerializer):
    """Read-only representation of a secretary for the doctor's list."""

    id = serializers.UUIDField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = Secretary
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'phone_number',
            'is_active',
            'created_at',
        ]
        read_only_fields = fields


class DoctorSecretaryCreateSerializer(serializers.Serializer):
    """Create a new secretary account linked to the requesting doctor."""

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(
        max_length=20,
        validators=[phone_number_validator],
    )
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value.lower()

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value

    def create(self, validated_data):
        doctor = self.context['doctor']
        user = User.objects.create_user(
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password'],
            user_type='secretary',
            is_verified=True,
        )
        secretary = Secretary.objects.create(
            user=user,
            doctor=doctor,
            phone_number=validated_data['phone_number'],
        )
        return secretary


class DoctorSecretaryUpdateSerializer(serializers.Serializer):
    """Update an existing secretary (toggle active status, phone)."""

    phone_number = serializers.CharField(
        max_length=20,
        validators=[phone_number_validator],
        required=False,
    )
    is_active = serializers.BooleanField(required=False)


# ═══════════════════════════════════════════════════════════════════════
# Doctor – Reviews
# ═══════════════════════════════════════════════════════════════════════


class DoctorReviewSerializer(serializers.ModelSerializer):
    """Reviews received by the doctor (read-only)."""

    patient_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = DoctorReview
        fields = [
            'id',
            'patient_name',
            'rating',
            'comment',
            'created_at',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════════════
# Doctor – Analytics
# ═══════════════════════════════════════════════════════════════════════


class DoctorAnalyticsSerializer(serializers.Serializer):
    """Per-doctor analytics / stats."""

    total_appointments = serializers.IntegerField()
    pending_appointments = serializers.IntegerField()
    completed_appointments = serializers.IntegerField()
    cancelled_appointments = serializers.IntegerField()
    total_patients = serializers.IntegerField()
    total_reviews = serializers.IntegerField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=1)
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    appointments_this_month = serializers.IntegerField()
    revenue_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)


# ═══════════════════════════════════════════════════════════════════════
# Secretary – Doctor (read-only)
# ═══════════════════════════════════════════════════════════════════════


class SecretaryDoctorSerializer(serializers.ModelSerializer):
    """Read-only info about the doctor the secretary is assigned to."""

    id = serializers.UUIDField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = Doctor
        fields = [
            'id',
            'email',
            'full_name',
            'phone_number',
            'specialty',
            'rating',
            'total_reviews',
            'profile_image_url',
            'bio',
            'location',
            'working_hours',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════════════
# Secretary – Appointments
# ═══════════════════════════════════════════════════════════════════════


class SecretaryAppointmentServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorService
        fields = ['id', 'name', 'price']


class SecretaryAppointmentSerializer(serializers.ModelSerializer):
    """
    Appointments for the secretary's assigned doctor.
    Same shape as doctor appointments but fully read-only.
    """

    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    patient_email = serializers.EmailField(source='patient.email', read_only=True)
    patient_id = serializers.UUIDField(source='patient.id', read_only=True)
    services = SecretaryAppointmentServiceSerializer(many=True, read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_id',
            'patient_name',
            'patient_email',
            'date',
            'time_slot',
            'status',
            'total_price',
            'notes',
            'services',
            'created_at',
        ]
        read_only_fields = fields
