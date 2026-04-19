from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.dashboard.models import AuditLog
from apps.users.models import AdminRole, AdminRoleAssignment, Doctor

User = get_user_model()


class AdminIntegrationTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            password="StrongPass123!",
            user_type="admin",
            is_verified=True,
        )
        self.role = AdminRole.objects.create(name="Super Admin Test", is_system=True)
        AdminRoleAssignment.objects.create(user=self.admin_user, role=self.role)

        self.doctor_user = User.objects.create_user(
            email="doctor@example.com",
            first_name="Doctor",
            last_name="User",
            password="StrongPass123!",
            user_type="doctor",
            is_verified=True,
            is_active=True,
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            phone_number="+201000000000",
            specialty="Ortho",
        )

        self.non_admin = User.objects.create_user(
            email="patient@example.com",
            first_name="Patient",
            last_name="User",
            password="StrongPass123!",
            user_type="patient",
            is_verified=True,
        )

    def _auth_admin(self):
        self.client.force_authenticate(user=self.admin_user)

    def test_get_admin_audit_success_and_envelope(self):
        AuditLog.objects.create(
            user=self.admin_user,
            action="user_updated",
            target_type="User",
            target_id=str(self.doctor_user.id),
            description="Updated user",
        )
        self._auth_admin()
        url = "/api/v1/dashboard/admin/audit/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        self.assertIn("meta", response.data)
        self.assertIsInstance(response.data["data"], list)

    def test_get_admin_audit_permission_denied_for_non_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.get("/api/v1/dashboard/admin/audit/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)

    def test_post_syndicate_sync_success_and_envelope(self):
        self._auth_admin()
        payload = [
            {
                "email": "doctor@example.com",
                "license_status": "suspended",
                "specialty": "Ortho",
                "location": "Cairo",
            }
        ]
        response = self.client.post(
            "/api/v1/dashboard/admin/syndicate/sync/",
            data=payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="sync-1",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        self.assertEqual(response.data["data"]["status"], "queued")
        self.assertIn("task_id", response.data["data"])

    def test_post_syndicate_sync_idempotency_returns_same_response(self):
        self._auth_admin()
        payload = [{"email": "doctor@example.com", "license_status": "suspended"}]
        headers = {"HTTP_IDEMPOTENCY_KEY": "sync-fixed-key"}

        response1 = self.client.post(
            "/api/v1/dashboard/admin/syndicate/sync/",
            data=payload,
            format="json",
            **headers,
        )
        response2 = self.client.post(
            "/api/v1/dashboard/admin/syndicate/sync/",
            data=payload,
            format="json",
            **headers,
        )

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data, response2.data)

    def test_patch_admin_doctor_profile_success_and_envelope(self):
        self._auth_admin()
        url = f"/api/v1/dashboard/admin/doctors/{self.doctor_user.id}/profile/"
        response = self.client.patch(
            url,
            data={"specialty": "Implants", "location": "Alex"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        self.assertIn("error", response.data)
        self.assertIsNone(response.data["error"])

        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.specialty, "Implants")
        self.assertEqual(self.doctor.location, "Alex")

    def test_patch_admin_doctor_profile_denied_for_non_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        url = f"/api/v1/dashboard/admin/doctors/{self.doctor_user.id}/profile/"
        response = self.client.patch(url, data={"specialty": "Implants"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)
