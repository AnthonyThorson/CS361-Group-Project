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

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Class not found')