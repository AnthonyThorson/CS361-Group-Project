from django.contrib.auth import get_user_model
from django.test import TestCase


class AdminLoginTests(TestCase):
    def test_admin_requires_login(self):
        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/admin/login/?next=/admin/')

    def test_superuser_can_access_admin(self):
        user_model = get_user_model()
        user_model.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='test-password-123',
        )
        self.client.login(username='admin', password='test-password-123')

        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, 200)

    def test_admin_login_page_is_available(self):
        response = self.client.get('/admin/login/')

        self.assertEqual(response.status_code, 200)
