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
