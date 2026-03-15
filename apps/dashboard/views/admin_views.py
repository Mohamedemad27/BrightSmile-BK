from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import (
    Appointment,
    DoctorReview,
    HealthTip,
    ServiceCategory,
)
from apps.users.models import (
    AdminRole,
    AdminRoleAssignment,
    Doctor,
)
from apps.users.permissions import (
    ADMIN_PERMISSION_CODENAMES,
    HasDashboardPermission,
    IsAdmin,
)
from apps.dashboard.serializers.dashboard_serializers import (
    AdminAppointmentListSerializer,
    AdminCategorySerializer,
    AdminDoctorListSerializer,
    AdminHealthTipSerializer,
    AdminReviewListSerializer,
    AdminRoleAssignSerializer,
    AdminRoleSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
)

User = get_user_model()


# ──────────────────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────────────────


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ──────────────────────────────────────────────────────────────────────
# User management
# ──────────────────────────────────────────────────────────────────────


class AdminUserListView(APIView):
    """List all users with search & filter support."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'view_all_users'

    def get(self, request):
        qs = User.objects.all()

        # Search
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        # Filters
        user_type = request.query_params.get('user_type')
        if user_type:
            qs = qs.filter(user_type=user_type)

        is_active = request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ('true', '1'))

        qs = qs.order_by('-created_at')

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminUserListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminUserDetailView(APIView):
    """Get or partially update a single user."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'manage_users'

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AdminUserDetailSerializer(user).data)

    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminUserDetailSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ──────────────────────────────────────────────────────────────────────
# Doctor management
# ──────────────────────────────────────────────────────────────────────


class AdminDoctorListView(APIView):
    """List all doctors with specialty, rating, and approval status."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'view_all_users'

    def get(self, request):
        qs = (
            Doctor.objects
            .select_related('user')
            .order_by('-created_at')
        )

        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(specialty__icontains=search)
            )

        is_active = request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(user__is_active=is_active.lower() in ('true', '1'))

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminDoctorListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminDoctorApproveView(APIView):
    """Approve a doctor by activating their user account."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'approve_doctors'

    def patch(self, request, doctor_id):
        try:
            doctor = Doctor.objects.select_related('user').get(user_id=doctor_id)
        except Doctor.DoesNotExist:
            return Response(
                {'detail': 'Doctor not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = doctor.user
        if user.is_active:
            return Response(
                {'detail': 'Doctor is already approved.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = True
        user.save(update_fields=['is_active', 'updated_at'])

        return Response({'detail': 'Doctor approved successfully.'})


# ──────────────────────────────────────────────────────────────────────
# Appointments
# ──────────────────────────────────────────────────────────────────────


class AdminAppointmentListView(APIView):
    """List all appointments with filters."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'view_all_appointments'

    def get(self, request):
        qs = (
            Appointment.objects
            .select_related('doctor__user', 'patient')
            .prefetch_related('services')
        )

        # Filters
        appt_status = request.query_params.get('status')
        if appt_status:
            qs = qs.filter(status=appt_status)

        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(date__lte=date_to)

        doctor_id = request.query_params.get('doctor')
        if doctor_id:
            qs = qs.filter(doctor__user_id=doctor_id)

        patient_id = request.query_params.get('patient')
        if patient_id:
            qs = qs.filter(patient_id=patient_id)

        qs = qs.order_by('-date', '-created_at')

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminAppointmentListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ──────────────────────────────────────────────────────────────────────
# Reviews
# ──────────────────────────────────────────────────────────────────────


class AdminReviewListView(APIView):
    """List all reviews."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'view_all_reviews'

    def get(self, request):
        qs = (
            DoctorReview.objects
            .select_related('doctor__user', 'user', 'appointment')
            .order_by('-created_at')
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminReviewListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminReviewDeleteView(APIView):
    """Delete (moderate) a review."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'moderate_reviews'

    def delete(self, request, review_id):
        try:
            review = DoctorReview.objects.select_related('doctor').get(id=review_id)
        except DoctorReview.DoesNotExist:
            return Response(
                {'detail': 'Review not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        doctor = review.doctor
        review.delete()

        # Recalculate doctor rating
        reviews = DoctorReview.objects.filter(doctor=doctor)
        total = reviews.count()
        avg = sum(r.rating for r in reviews) / total if total else 0
        Doctor.objects.filter(user=doctor.user).update(
            rating=round(avg, 1),
            total_reviews=total,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────────────────
# Service categories
# ──────────────────────────────────────────────────────────────────────


class AdminCategoryListCreateView(APIView):
    """List and create service categories."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'manage_categories'

    def get(self, request):
        qs = ServiceCategory.objects.all().order_by('name')
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminCategorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = AdminCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(APIView):
    """Update or delete a service category."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'manage_categories'

    def patch(self, request, category_id):
        try:
            category = ServiceCategory.objects.get(id=category_id)
        except ServiceCategory.DoesNotExist:
            return Response(
                {'detail': 'Category not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminCategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, category_id):
        try:
            category = ServiceCategory.objects.get(id=category_id)
        except ServiceCategory.DoesNotExist:
            return Response(
                {'detail': 'Category not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────────────────
# Health tips
# ──────────────────────────────────────────────────────────────────────


class AdminHealthTipListCreateView(APIView):
    """List and create health tips."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'manage_health_tips'

    def get(self, request):
        qs = HealthTip.objects.all().order_by('-created_at')
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminHealthTipSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = AdminHealthTipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminHealthTipDetailView(APIView):
    """Update or delete a health tip."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'manage_health_tips'

    def patch(self, request, tip_id):
        try:
            tip = HealthTip.objects.get(id=tip_id)
        except HealthTip.DoesNotExist:
            return Response(
                {'detail': 'Health tip not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminHealthTipSerializer(tip, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, tip_id):
        try:
            tip = HealthTip.objects.get(id=tip_id)
        except HealthTip.DoesNotExist:
            return Response(
                {'detail': 'Health tip not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        tip.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────────────────────────────


class AdminAnalyticsView(APIView):
    """Return platform-wide statistics."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'view_analytics'

    def get(self, request):
        today = date.today()

        data = {
            'total_users': User.objects.count(),
            'total_doctors': User.objects.filter(user_type='doctor').count(),
            'total_patients': User.objects.filter(user_type='patient').count(),
            'total_appointments': Appointment.objects.count(),
            'appointments_today': Appointment.objects.filter(date=today).count(),
            'pending_doctor_approvals': User.objects.filter(
                user_type='doctor',
                is_active=False,
            ).count(),
        }

        return Response(data)


# ──────────────────────────────────────────────────────────────────────
# Admin roles
# ──────────────────────────────────────────────────────────────────────


class AdminRoleListCreateView(APIView):
    """List and create admin roles."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'manage_roles'

    def get(self, request):
        qs = AdminRole.objects.prefetch_related('permissions').order_by('name')
        serializer = AdminRoleSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AdminRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            AdminRoleSerializer(serializer.instance).data,
            status=status.HTTP_201_CREATED,
        )


class AdminRoleDetailView(APIView):
    """Get, update, or delete an admin role."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'manage_roles'

    def get(self, request, role_id):
        try:
            role = AdminRole.objects.prefetch_related('permissions').get(id=role_id)
        except AdminRole.DoesNotExist:
            return Response(
                {'detail': 'Role not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AdminRoleSerializer(role).data)

    def patch(self, request, role_id):
        try:
            role = AdminRole.objects.prefetch_related('permissions').get(id=role_id)
        except AdminRole.DoesNotExist:
            return Response(
                {'detail': 'Role not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminRoleSerializer(role, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminRoleSerializer(serializer.instance).data)

    def delete(self, request, role_id):
        try:
            role = AdminRole.objects.get(id=role_id)
        except AdminRole.DoesNotExist:
            return Response(
                {'detail': 'Role not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if role.is_system:
            return Response(
                {'detail': 'System roles cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminRoleAssignView(APIView):
    """Assign an admin user to a role."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'manage_roles'

    def post(self, request):
        serializer = AdminRoleAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        role_id = serializer.validated_data['role_id']

        try:
            user = User.objects.get(id=user_id, user_type='admin')
        except User.DoesNotExist:
            return Response(
                {'detail': 'Admin user not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            role = AdminRole.objects.get(id=role_id)
        except AdminRole.DoesNotExist:
            return Response(
                {'detail': 'Role not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        assignment, created = AdminRoleAssignment.objects.update_or_create(
            user=user,
            defaults={'role': role},
        )

        return Response(
            {
                'detail': 'Role assigned successfully.',
                'user_id': str(user.id),
                'role_id': str(role.id),
                'role_name': role.name,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AdminRolePermissionsView(APIView):
    """Return the list of all assignable admin permission codenames."""

    permission_classes = [IsAuthenticated, IsAdmin, HasDashboardPermission]
    required_permission = 'manage_roles'

    def get(self, request):
        return Response({'permissions': ADMIN_PERMISSION_CODENAMES})
