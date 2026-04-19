from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.decorators import method_decorator
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.models import Appointment, DoctorReview, HealthTip, ServiceCategory
from apps.dashboard.permissions import AdminDashboardPermission
from apps.dashboard.serializers.dashboard_serializers import (
    AdminAppointmentListSerializer,
    AdminAuditEntrySerializer,
    AdminCategorySerializer,
    AdminDoctorListSerializer,
    AdminDoctorProfileUpdateSerializer,
    AdminHealthTipSerializer,
    AdminReviewListSerializer,
    AdminRoleSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
    SyndicateDoctorPayloadSerializer,
)
from apps.dashboard.services import (
    AdminUserService,
    AuditService,
    DashboardCacheService,
)
from apps.dashboard.tasks import sync_syndicate_task
from apps.users.models import AdminRole, AdminRoleAssignment, Doctor
from apps.users.permissions import ADMIN_PERMISSION_CODENAMES
from utils.api_response import api_success
from utils.feature_flags import is_feature_enabled
from utils.idempotency import idempotent_endpoint
from utils.pagination import StandardizedPagination

User = get_user_model()


class StandardPagination(StandardizedPagination):
    page_size = 20


class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'view_all_users'

    def get(self, request):
        qs = User.objects.all()

        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

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
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'manage_users'

    def get(self, request, pk):
        user = AdminUserService.get_user_or_none(pk)
        if user is None:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, user)
        return Response(AdminUserDetailSerializer(user).data)

    def patch(self, request, pk):
        user = AdminUserService.get_user_or_none(pk)
        if user is None:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, user)

        serializer = AdminUserDetailSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='user_updated',
                target_type='User',
                target_id=user.id,
                description='Admin updated user.',
                ip_address=request.META.get('REMOTE_ADDR'),
                metadata={'fields': list(request.data.keys())},
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        return Response(serializer.data)


class AdminDoctorListView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'view_all_users'

    def get(self, request):
        cache_key = DashboardCacheService.make_key(
            'dashboard:admin:doctors',
            {'params': dict(request.query_params)},
        )

        def producer():
            qs = Doctor.objects.select_related('user').order_by('-created_at')

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
            return paginator.get_paginated_response(serializer.data).data

        return Response(DashboardCacheService.get_or_set(cache_key, producer, timeout=60))


class AdminDoctorApproveView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'approve_doctors'

    def patch(self, request, pk):
        doctor = AdminUserService.get_doctor_or_none(pk)
        if doctor is None:
            return Response({'detail': 'Doctor not found.'}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, doctor)

        if not AdminUserService.approve_doctor(doctor):
            return Response({'detail': 'Doctor is already approved.'}, status=status.HTTP_400_BAD_REQUEST)

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='doctor_approved',
                target_type='Doctor',
                target_id=doctor.user_id,
                description='Admin approved doctor.',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        DashboardCacheService.invalidate_prefix('dashboard:admin:doctors')
        DashboardCacheService.invalidate_prefix('dashboard:admin:analytics')
        return api_success(message='Doctor approved successfully.')


class AdminDoctorProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'manage_doctor_profiles'

    def patch(self, request, pk):
        doctor = AdminUserService.get_doctor_or_none(pk)
        if doctor is None:
            return Response({'detail': 'Doctor not found.'}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, doctor)

        serializer = AdminDoctorProfileUpdateSerializer(doctor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='doctor_profile_updated',
                target_type='Doctor',
                target_id=doctor.user_id,
                description='Admin updated doctor profile.',
                ip_address=request.META.get('REMOTE_ADDR'),
                metadata={'fields': list(request.data.keys())},
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        DashboardCacheService.invalidate_prefix('dashboard:admin:doctors')
        return api_success(data=AdminDoctorListSerializer(doctor).data, message='Doctor profile updated successfully.')


class AdminAppointmentListView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'view_all_appointments'

    def get(self, request):
        qs = Appointment.objects.select_related('doctor__user', 'patient').prefetch_related('services')

        # Search by patient name, patient email, or doctor name
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(patient__first_name__icontains=search)
                | Q(patient__last_name__icontains=search)
                | Q(patient__email__icontains=search)
                | Q(doctor__user__first_name__icontains=search)
                | Q(doctor__user__last_name__icontains=search)
            )

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


class AdminReviewListView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'view_all_reviews'

    def get(self, request):
        qs = DoctorReview.objects.select_related('doctor__user', 'user', 'appointment').order_by('-created_at')
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminReviewListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminReviewDeleteView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'moderate_reviews'

    def delete(self, request, pk):
        try:
            review = DoctorReview.objects.select_related('doctor').get(id=pk)
        except DoctorReview.DoesNotExist:
            return Response({'detail': 'Review not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, review)
        doctor = review.doctor
        review.delete()

        reviews = DoctorReview.objects.filter(doctor=doctor)
        total = reviews.count()
        avg = sum(r.rating for r in reviews) / total if total else 0
        Doctor.objects.filter(user=doctor.user).update(rating=round(avg, 1), total_reviews=total)

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='review_deleted',
                target_type='DoctorReview',
                target_id=pk,
                description='Admin deleted review.',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        DashboardCacheService.invalidate_prefix('dashboard:admin:doctors')
        return api_success(message='Review deleted successfully.')


class AdminCategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
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
        category = serializer.save()

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='category_created',
                target_type='ServiceCategory',
                target_id=category.id,
                description='Admin created category.',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'manage_categories'

    def patch(self, request, pk):
        try:
            category = ServiceCategory.objects.get(id=pk)
        except ServiceCategory.DoesNotExist:
            return Response({'detail': 'Category not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, category)
        serializer = AdminCategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='category_updated',
                target_type='ServiceCategory',
                target_id=category.id,
                description='Admin updated category.',
                ip_address=request.META.get('REMOTE_ADDR'),
                metadata={'fields': list(request.data.keys())},
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        return Response(serializer.data)

    def delete(self, request, pk):
        try:
            category = ServiceCategory.objects.get(id=pk)
        except ServiceCategory.DoesNotExist:
            return Response({'detail': 'Category not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, category)
        category.delete()

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='category_deleted',
                target_type='ServiceCategory',
                target_id=pk,
                description='Admin deleted category.',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        return api_success(message='Category deleted successfully.')


class AdminHealthTipListCreateView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
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
        tip = serializer.save()

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='health_tip_created',
                target_type='HealthTip',
                target_id=tip.id,
                description='Admin created health tip.',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminHealthTipDetailView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'manage_health_tips'

    def patch(self, request, pk):
        try:
            tip = HealthTip.objects.get(id=pk)
        except HealthTip.DoesNotExist:
            return Response({'detail': 'Health tip not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, tip)
        serializer = AdminHealthTipSerializer(tip, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='health_tip_updated',
                target_type='HealthTip',
                target_id=tip.id,
                description='Admin updated health tip.',
                ip_address=request.META.get('REMOTE_ADDR'),
                metadata={'fields': list(request.data.keys())},
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        return Response(serializer.data)

    def delete(self, request, pk):
        try:
            tip = HealthTip.objects.get(id=pk)
        except HealthTip.DoesNotExist:
            return Response({'detail': 'Health tip not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, tip)
        tip.delete()

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='health_tip_deleted',
                target_type='HealthTip',
                target_id=pk,
                description='Admin deleted health tip.',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        return api_success(message='Health tip deleted successfully.')


class AdminAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'view_analytics'

    def get(self, request):
        cache_key = DashboardCacheService.make_key('dashboard:admin:analytics', {'date': str(date.today())})

        def producer():
            today = date.today()
            return {
                'total_users': User.objects.count(),
                'total_doctors': User.objects.filter(user_type='doctor').count(),
                'total_patients': User.objects.filter(user_type='patient').count(),
                'total_appointments': Appointment.objects.count(),
                'appointments_today': Appointment.objects.filter(date=today).count(),
                'pending_doctor_approvals': User.objects.filter(user_type='doctor', is_active=False).count(),
            }

        return Response(DashboardCacheService.get_or_set(cache_key, producer, timeout=120))


class AdminRoleListCreateView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'manage_roles'

    def get(self, request):
        qs = AdminRole.objects.prefetch_related('permissions').order_by('name')
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminRoleSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = AdminRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminRoleSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)


class AdminRoleDetailView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'manage_roles'

    def get(self, request, pk):
        try:
            role = AdminRole.objects.prefetch_related('permissions').get(id=pk)
        except AdminRole.DoesNotExist:
            return Response({'detail': 'Role not found.'}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, role)
        return Response(AdminRoleSerializer(role).data)

    def patch(self, request, pk):
        try:
            role = AdminRole.objects.prefetch_related('permissions').get(id=pk)
        except AdminRole.DoesNotExist:
            return Response({'detail': 'Role not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, role)
        serializer = AdminRoleSerializer(role, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='role_updated',
                target_type='AdminRole',
                target_id=role.id,
                description='Admin updated role.',
                ip_address=request.META.get('REMOTE_ADDR'),
                metadata={'fields': list(request.data.keys())},
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        return Response(AdminRoleSerializer(serializer.instance).data)

    def delete(self, request, pk):
        try:
            role = AdminRole.objects.get(id=pk)
        except AdminRole.DoesNotExist:
            return Response({'detail': 'Role not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, role)
        if role.is_system:
            return Response({'detail': 'System roles cannot be deleted.'}, status=status.HTTP_400_BAD_REQUEST)

        role.delete()
        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='role_deleted',
                target_type='AdminRole',
                target_id=pk,
                description='Admin deleted role.',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        return api_success(message='Role deleted successfully.')


class AdminRoleAssignView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'manage_roles'

    class InputSerializer(serializers.Serializer):
        user_id = serializers.UUIDField()

    def post(self, request, pk):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']

        try:
            user = User.objects.get(id=user_id, user_type='admin')
        except User.DoesNotExist:
            return Response({'detail': 'Admin user not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            role = AdminRole.objects.get(id=pk)
        except AdminRole.DoesNotExist:
            return Response({'detail': 'Role not found.'}, status=status.HTTP_404_NOT_FOUND)

        assignment, created = AdminRoleAssignment.objects.update_or_create(user=user, defaults={'role': role})

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='role_assigned',
                target_type='AdminRoleAssignment',
                target_id=assignment.id,
                description='Admin assigned role to user.',
                ip_address=request.META.get('REMOTE_ADDR'),
                metadata={'user_id': str(user.id), 'role_id': str(role.id)},
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

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
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'manage_roles'

    def get(self, request):
        return Response({'permissions': ADMIN_PERMISSION_CODENAMES})


class AdminAuditListView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'view_analytics'

    def get(self, request):
        # Audit feed should reflect writes immediately; avoid stale cache.
        entries_qs = AuditService.get_entries_queryset(
            search=request.query_params.get('search', '').strip(),
            action=request.query_params.get('action', '').strip(),
            date_from=request.query_params.get('date_from') or None,
            date_to=request.query_params.get('date_to') or None,
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(entries_qs, request)
        serializer = AdminAuditEntrySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminSyndicateSyncView(APIView):
    permission_classes = [IsAuthenticated, AdminDashboardPermission]
    required_permission = 'manage_doctor_profiles'
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'admin_sync'

    @method_decorator(idempotent_endpoint(timeout_seconds=getattr(settings, 'IDEMPOTENCY_CACHE_TTL_SECONDS', 3600)))
    def post(self, request):
        if not is_feature_enabled('enable_syndicate_sync', True):
            return api_success(data={'status': 'disabled'}, message='Syndicate sync feature is disabled.')

        incoming_payload = request.data if isinstance(request.data, list) else []
        if incoming_payload:
            serializer = SyndicateDoctorPayloadSerializer(data=incoming_payload, many=True)
            serializer.is_valid(raise_exception=True)
            payload = serializer.validated_data
        else:
            payload = None

        task = sync_syndicate_task.delay(
            payload=payload,
            triggered_by_user_id=str(request.user.id),
        )

        if is_feature_enabled('enable_audit_logging', True):
            AuditService.log_action(
                user=request.user,
                action='syndicate_sync_queued',
                target_type='Syndicate',
                target_id=task.id,
                description='Admin queued syndicate sync task.',
                ip_address=request.META.get('REMOTE_ADDR'),
                metadata={'queued': True},
            )
            DashboardCacheService.invalidate_prefix('dashboard:admin:audit')

        return api_success(data={'task_id': task.id, 'status': 'queued'}, message='Syndicate sync queued.')
