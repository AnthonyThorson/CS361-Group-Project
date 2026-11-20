
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import NoReverseMatch, reverse


class DeleteAccountTests(TestCase):
    password = "A-strong-test-password-42!"

    def setUp(self):
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_superuser(
            username="administrator",
            email="admin@example.test",
            password=self.password,
        )
        self.client.force_login(self.admin)

        self.student_group, _ = Group.objects.get_or_create(name="Student")
        self.instructor_group, _ = Group.objects.get_or_create(name="Instructor")

        self.target_user = self.user_model.objects.create_user(
            username="target-student",
            first_name="Charles Babbage",
            email="charles@example.test",
            password=self.password,
        )
        self.target_user.groups.add(self.student_group)

    def delete_url(self, user_id):
        try:
            return reverse("delete_account", args=[user_id])
        except NoReverseMatch:
            return f"/staff/{user_id}/delete/"

    def test_administrator_can_delete_account_and_block_login(self):
        target_id = self.target_user.pk
        target_username = self.target_user.username

        response = self.client.post(self.delete_url(target_id), follow=True)

        self.assertIn(response.status_code, (200, 302, 404))

        # Verify the account is either deleted or deactivated/no longer active
        remaining_qs = self.user_model.objects.filter(pk=target_id)
        if remaining_qs.exists():
            account = remaining_qs.get()
            self.assertFalse(account.is_active)
        self.assertFalse(
            self.user_model.objects.filter(pk=target_id, is_active=True).exists()
        )

        # Verify the account can no longer authenticate / log in
        auth_user = authenticate(
            self.client.wsgi_request if hasattr(self.client, "wsgi_request") else None,
            username=target_username,
            password=self.password,
        )
        self.assertIsNone(auth_user)

    def test_unauthorized_user_cannot_delete_account(self):
        non_admin = self.user_model.objects.create_user(
            username="regular-instructor",
            email="instructor@example.test",
            password=self.password,
            is_staff=True,
        )
        non_admin.groups.add(self.instructor_group)
        self.client.force_login(non_admin)

        response = self.client.post(self.delete_url(self.target_user.pk), follow=False)

        self.assertIn(response.status_code, (302, 403))
        self.assertTrue(self.user_model.objects.filter(pk=self.target_user.pk).exists())
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_active)
