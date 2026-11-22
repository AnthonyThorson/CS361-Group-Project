from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import NoReverseMatch, reverse


class EditAccountInformationTests(TestCase):
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

        self.account = self.user_model.objects.create_user(
            username="ada-staff",
            first_name="Ada Lovelace",
            email="ada@example.test",
            password=self.password,
            is_staff=True,
        )
        self.account.groups.add(self.instructor_group)

    def edit_url(self, user_id):
        try:
            return reverse("edit_account", args=[user_id])
        except NoReverseMatch:
            return f"/staff/{user_id}/edit/"

    def post_edit(
        self,
        user_id,
        *,
        name="Ada Byron",
        email="ada.byron@example.test",
        role="ta",
    ):
        return self.client.post(
            self.edit_url(user_id),
            {"name": name, "email": email, "role": role},
            follow=True,
        )

    def response_text(self, response):
        messages = " ".join(
            str(message) for message in get_messages(response.wsgi_request)
        )
        return f"{response.content.decode(errors='replace')} {messages}".lower()

    def test_successfully_edit_account_stores_and_displays_updated_info(self):
        response = self.post_edit(
            self.account.pk,
            name="Ada Byron",
            email="ada.byron@example.test",
            role="ta",
        )

        self.assertEqual(response.status_code, 200)

        self.account.refresh_from_db()
        self.assertEqual(self.account.first_name, "Ada Byron")
        self.assertEqual(self.account.email, "ada.byron@example.test")
        self.assertTrue(self.account.groups.filter(name="TA").exists())
        self.assertFalse(self.account.groups.filter(name="Instructor").exists())

        page_and_messages = self.response_text(response)
        self.assertIn("ada byron", page_and_messages)
        self.assertIn("ada.byron@example.test", page_and_messages)

    def test_unsuccessfully_edit_account_does_not_store_and_shows_retry_popup(self):
        with patch.object(
            self.user_model, "save", side_effect=Exception("Database failure")
        ):
            response = self.post_edit(
                self.account.pk,
                name="Updated Name",
                email="updated@example.test",
                role="ta",
            )

        self.account.refresh_from_db()
        self.assertEqual(self.account.first_name, "Ada Lovelace")
        self.assertEqual(self.account.email, "ada@example.test")
        self.assertTrue(self.account.groups.filter(name="Instructor").exists())
        self.assertIn(
            "unsuccessful edits try again later", self.response_text(response)
        )

    def test_edit_nonexistent_account_changes_nothing_and_informs_admin(self):
        missing_id = 999999
        self.assertFalse(self.user_model.objects.filter(pk=missing_id).exists())
        initial_count = self.user_model.objects.count()

        response = self.post_edit(missing_id)

        self.assertEqual(self.user_model.objects.count(), initial_count)
        self.account.refresh_from_db()
        self.assertEqual(self.account.first_name, "Ada Lovelace")
        self.assertEqual(self.account.email, "ada@example.test")

        text = self.response_text(response)
        self.assertTrue(
            any(
                phrase in text
                for phrase in ("could not be found", "not found", "does not exist")
            )
        )

    def test_blank_fields_fail_edit_and_show_missing_field_popup(self):
        blank_submissions = [
            {"name": "", "email": "ada.byron@example.test", "role": "ta"},
            {"name": "Ada Byron", "email": "", "role": "ta"},
            {"name": "Ada Byron", "email": "ada.byron@example.test", "role": ""},
        ]

        for payload in blank_submissions:
            with self.subTest(payload=payload):
                response = self.client.post(
                    self.edit_url(self.account.pk),
                    payload,
                    follow=True,
                )

                self.account.refresh_from_db()
                self.assertEqual(self.account.first_name, "Ada Lovelace")
                self.assertEqual(self.account.email, "ada@example.test")
                self.assertTrue(self.account.groups.filter(name="Instructor").exists())
                self.assertIn("missing field pop up", self.response_text(response))
