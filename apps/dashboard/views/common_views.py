from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class DashboardMeView(APIView):
    """
    Returns the current authenticated user's info, role, and permissions
    for the dashboard shell (sidebar, role badge, etc.).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        data = {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'user_type': user.user_type,
            'permissions': self._resolve_permissions(user),
        }

        # Include assigned doctor info for secretaries
        if user.user_type == 'secretary':
            try:
                secretary = user.secretary_profile
                data['assigned_doctor'] = {
                    'id': str(secretary.doctor.user_id),
                    'name': secretary.doctor.full_name,
                    'email': secretary.doctor.email,
                }
            except Exception:
                data['assigned_doctor'] = None

        return Response(data)

    # ------------------------------------------------------------------
    # Permission resolution helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_permissions(user):
        """
        Return a flat list of permission codename strings depending on
        the user type.

        * admin  -> AdminRoleAssignment -> AdminRole -> permissions (codenames)
        * doctor / secretary -> Django Group permissions (codenames)
        """
        if user.user_type == 'admin':
            return DashboardMeView._admin_permissions(user)
        if user.user_type in ('doctor', 'secretary'):
            return DashboardMeView._group_permissions(user)
        return []

    @staticmethod
    def _admin_permissions(user):
        assignment = getattr(user, 'admin_role_assignment', None)
        if assignment is None:
            return []

        # Super-admin (system role) gets a special marker so the
        # frontend knows this user has *all* permissions.
        if assignment.role.is_system:
            from apps.users.permissions import ADMIN_PERMISSION_CODENAMES
            return list(ADMIN_PERMISSION_CODENAMES)

        return list(
            assignment.role.permissions
            .values_list('codename', flat=True)
        )

    @staticmethod
    def _group_permissions(user):
        # get_group_permissions() returns 'app_label.codename';
        # strip the app_label prefix for consistency.
        return [
            perm.split('.')[-1]
            for perm in user.get_group_permissions()
        ]
