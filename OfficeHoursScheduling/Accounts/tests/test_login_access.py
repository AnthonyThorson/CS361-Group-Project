from django.test import TestCase
from django.contrib.auth import authenticate, get_user_model


class AccountUserTests(TestCase):
    def setUp(self):
        self.email = "person@example.com"
        self.password = "test-password-123"
        self.user = get_user_model().objects.create_user(
            email=self.email,
            password=self.password,
        )

    def test_email_is_the_login_identifier(self):
        user_model = get_user_model()
        self.assertEqual(user_model.USERNAME_FIELD, "email")
        self.assertNotIn(
            "username",
            [field.name for field in user_model._meta.get_fields()],
        )

    def test_password_is_stored_as_a_hash(self):
        self.assertNotEqual(self.user.password, self.password)
        self.assertTrue(self.user.check_password(self.password))

    def test_authenticate_with_email_and_password(self):
        authenticated_user = authenticate(
            email=self.email,
            password=self.password,
        )

        self.assertEqual(authenticated_user, self.user)

    def test_authentication_rejects_wrong_password(self):
        authenticated_user = authenticate(
            email=self.email,
            password="wrong-password",
        )

        self.assertIsNone(authenticated_user)

    def test_create_user_requires_email(self):
        with self.assertRaisesMessage(ValueError, "An email address is required."):
            get_user_model().objects.create_user(email="", password=self.password)

    def test_create_user_normalizes_email_domain(self):
        user = get_user_model().objects.create_user(
            email="normalized@EXAMPLE.COM",
            password=self.password,
        )

        self.assertEqual(user.email, "normalized@example.com")

    def test_user_without_password_cannot_authenticate(self):
        user = get_user_model().objects.create_user(email="no-password@example.com")

        self.assertFalse(user.has_usable_password())
        self.assertIsNone(
            authenticate(email="no-password@example.com", password=self.password)
        )

    def test_inactive_user_cannot_authenticate(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.assertIsNone(authenticate(email=self.email, password=self.password))

    def test_create_superuser_sets_staff_and_superuser_flags(self):
        superuser = get_user_model().objects.create_superuser(
            email="admin@example.com",
            password=self.password,
        )

        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)

    def test_create_superuser_rejects_is_staff_false(self):
        with self.assertRaisesMessage(ValueError, "A superuser must have is_staff=True."):
            get_user_model().objects.create_superuser(
                email="admin@example.com",
                password=self.password,
                is_staff=False,
            )

    def test_create_superuser_rejects_is_superuser_false(self):
        with self.assertRaisesMessage(
            ValueError, "A superuser must have is_superuser=True."
        ):
            get_user_model().objects.create_superuser(
                email="admin@example.com",
                password=self.password,
                is_superuser=False,
            )
