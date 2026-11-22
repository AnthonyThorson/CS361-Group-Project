
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import NoReverseMatch, reverse


class CreateStaffAccountTests(TestCase):
    password = "A-strong-test-password-42!"

    def setUp(self):
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_superuser(
            username="administrator",
            email="admin@example.test",
            password=self.password,
        )
        self.client.force_login(self.admin)

        self.instructor_group, _ = Group.objects.get_or_create(name="Instructor")
        self.ta_group, _ = Group.objects.get_or_create(name="TA")
        self.student_group, _ = Group.objects.get_or_create(name="Student")

    def create_staff_url(self):
        try:
            return reverse("create_staff_account")
        except NoReverseMatch:
            return "/staff/create/"

    def post_staff(self, *, name="Ada Lovelace", email="ada@example.test", role="instructor"):
        return self.client.post(
            self.create_staff_url(),
            {"name": name, "email": email, "role": role},
            follow=True,
        )

    def response_text(self, response):
        messages = " ".join(str(message) for message in get_messages(response.wsgi_request))
        return f"{response.content.decode(errors='replace')} {messages}".lower()

    def test_successfully_create_instructor_and_ta_accounts(self):
        cases = [
            ("Ada Lovelace", "ada@example.test", "instructor", "Instructor"),
            ("Grace Hopper", "grace@example.test", "ta", "TA"),
        ]

        for name, email, role, expected_group in cases:
            with self.subTest(role=role):
                response = self.post_staff(name=name, email=email, role=role)
                self.assertEqual(response.status_code, 200)

                account = self.user_model.objects.get(email=email)
                self.assertEqual(account.first_name, name)
                self.assertTrue(account.is_staff)
                self.assertTrue(account.groups.filter(name=expected_group).exists())

    def test_duplicate_staff_account_is_not_created_and_reports_existence(self):
        self.user_model.objects.create_user(
            username="ada-existing",
            first_name="Ada Lovelace",
            email="ada@example.test",
            password=self.password,
            is_staff=True,
        )

        response = self.post_staff(name="Ada Lovelace", email="ada@example.test", role="instructor")

        self.assertEqual(self.user_model.objects.filter(email="ada@example.test").count(), 1)
        self.assertIn("already exists", self.response_text(response))

    def test_missing_or_invalid_information_does_not_create_account_and_shows_popup(self):
        invalid_payloads = [
            {"name": "", "email": "ada@example.test", "role": "instructor"},
            {"name": "Ada Lovelace", "email": "", "role": "instructor"},
            {"name": "Ada Lovelace", "email": "ada@example.test", "role": ""},
            {"name": "Ada Lovelace", "email": "ada@example.test", "role": "invalid_role"},
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(self.create_staff_url(), payload, follow=True)
                self.assertFalse(self.user_model.objects.filter(email="ada@example.test").exists())
                text = self.response_text(response)
                self.assertTrue(
                    any(term in text for term in ("pop up", "popup", "required", "invalid"))
                )

    def test_invalid_email_format_does_not_create_account_and_reports_email_error(self):
        bad_emails = ["ada.example.test", "ada@", "@example.test", "ada example.test"]

        for bad_email in bad_emails:
            with self.subTest(email=bad_email):
                response = self.post_staff(email=bad_email)
                self.assertFalse(self.user_model.objects.filter(email=bad_email).exists())
                text = self.response_text(response)
                self.assertTrue(
                    any(term in text for term in ("email", "valid", "pop up", "popup"))
                )

    def test_unauthorized_users_cannot_access_or_create_staff_accounts(self):
        non_admins = [
            ("student_user", "student@example.test", self.student_group),
            ("instructor_user", "inst@example.test", self.instructor_group),
            ("ta_user", "ta_user@example.test", self.ta_group),
        ]

        for username, email, group in non_admins:
            with self.subTest(role_group=group.name):
                user = self.user_model.objects.create_user(
                    username=username,
                    email=email,
                    password=self.password,
                    is_staff=(group.name in {"Instructor", "TA"}),
                )
                user.groups.add(group)
                self.client.force_login(user)

                get_response = self.client.get(self.create_staff_url(), follow=False)
                self.assertIn(get_response.status_code, (302, 403))

                post_response = self.client.post(
                    self.create_staff_url(),
                    {"name": "New Staff", "email": "new.staff@example.test", "role": "ta"},
                    follow=True,
                )
                self.assertFalse(
                    self.user_model.objects.filter(email="new.staff@example.test").exists()
                )
                self.assertIn(post_response.status_code, (200, 302, 403))
