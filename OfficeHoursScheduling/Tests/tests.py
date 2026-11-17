from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase

class StudentBooksAvailableSlotTests(OfficeHourTestBase):
    def test_student_receives_booking_confirmation_message(self):
        response = self.book_slot()

        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('booked' in m.lower() for m in messages))

    def test_slot_shows_as_booked_for_other_students(self):
        self.book_slot()

        self.login_as(self.other_student)
        response = self.client.get(
            reverse('scheduling:professor_slots', args=[self.professor.pk])
        )
        self.assertNotIn(self.slot, response.context['available_slots'])
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

class StudentBooksAvailableSlotTests(OfficeHourTestBase):
    def test_student_receives_booking_confirmation_message(self):
        response = self.book_slot()

        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('booked' in m.lower() for m in messages))

    def test_slot_shows_as_booked_for_other_students(self):
        self.book_slot()

        self.login_as(self.other_student)
        response = self.client.get(
            reverse('scheduling:professor_slots', args=[self.professor.pk])
        )
        self.assertNotIn(self.slot, response.context['available_slots'])

class ClassLookupTests(TestCase):
    def setUp(self):
        Course.objects.create(course_code='CS361')
        
    def test_class_lookup_page_loads(self):
        response = self.client.get('/classes/')

        self.assertEqual(response.status_code, 200)

    def test_class_lookup_empty_search(self):
        response = self.client.get('/classes/', {'course': ''})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a course')
        
    def test_class_lookup_valid_class(self):
        response = self.client.get('/classes/', {'course': 'CS361'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CS361')

    def test_class_lookup_invalid_class(self):
        response = self.client.get('/classes/', {'course': 'INVALID123'})

"""
Anthony's tests ->
"""
from django.contrib.auth import SESSION_KEY, get_user_model

class LoginAccessAcceptanceTests(TestCase):
    def test_anonymous_student_meetings_request_redirects_to_login(self):
        """B01 AC4 / P21 -> P01.

        Given I am not logged in,
        when I try to view office-hour meeting information,
        then I am redirected to login before that information is shown.
        """
        response = self.client.get("/meetings/")

        self.assertRedirects(
            response,
            "/login/?next=/meetings/",
            status_code=302,
            target_status_code=200,
        )
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_unknown_email_shows_login_error_and_does_not_log_in(self):
        """B01 AC3 / P01.

        Given no account exists for an email,
        when I submit that email and a password to login,
        then I see the generic login error and remain logged out.
        """
        email = "unregistered.student@example.test"
        self.assertFalse(get_user_model().objects.filter(email=email).exists())

        response = self.client.post(
            "/login/",
            {"email": email, "password": "NotARealAccountPassword42!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Incorrect email or password")
        self.assertIsNotNone(response.context)
        self.assertIn(
            "Incorrect email or password",
            " ".join(response.context["form_errors"]["__all__"]),
        )
        self.assertEqual(response.context["email_value"], email)
        self.assertIsNone(response.context["viewer"])
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Class not found')
    
    """
    End of my tests
    """
