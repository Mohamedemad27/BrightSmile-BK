from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class HealthCheckTestCase(TestCase):
    """
    Test cases for the health check endpoint.
    """

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.health_url = reverse('core:health_check')

    def test_health_check_endpoint_exists(self):
        """Test that health check endpoint is accessible."""
        response = self.client.get(self.health_url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])

    def test_health_check_response_structure(self):
        """Test that health check returns proper response structure."""
        response = self.client.get(self.health_url)
        data = response.json()

        # Check required fields
        self.assertIn('status', data)
        self.assertIn('timestamp', data)
        self.assertIn('services', data)
        self.assertIn('version', data)
        self.assertIn('environment', data)

        # Check status values
        self.assertIn(data['status'], ['healthy', 'degraded', 'unhealthy'])

        # Check services list
        self.assertIsInstance(data['services'], list)
        self.assertGreater(len(data['services']), 0)

    def test_health_check_service_structure(self):
        """Test that each service has proper structure."""
        response = self.client.get(self.health_url)
        data = response.json()

        for service in data['services']:
            self.assertIn('service', service)
            self.assertIn('status', service)
            self.assertIn('response_time', service)
            self.assertIn('details', service)
            self.assertIn(service['status'], ['healthy', 'unhealthy'])

    def test_health_check_includes_database(self):
        """Test that database check is included."""
        response = self.client.get(self.health_url)
        data = response.json()

        service_names = [s['service'] for s in data['services']]
        self.assertIn('database', service_names)

    def test_health_check_includes_redis(self):
        """Test that Redis check is included."""
        response = self.client.get(self.health_url)
        data = response.json()

        service_names = [s['service'] for s in data['services']]
        self.assertIn('redis', service_names)

    def test_health_check_includes_application(self):
        """Test that application check is included."""
        response = self.client.get(self.health_url)
        data = response.json()

        service_names = [s['service'] for s in data['services']]
        self.assertIn('application', service_names)

    def test_health_check_no_authentication_required(self):
        """Test that health check doesn't require authentication."""
        # Test without any authentication
        response = self.client.get(self.health_url)
        # Should not return 401 or 403
        self.assertNotIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
