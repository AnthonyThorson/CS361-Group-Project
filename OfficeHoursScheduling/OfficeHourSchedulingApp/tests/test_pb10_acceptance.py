"""PB-10 acceptance tests: Propose office hours for my courses.

One test per acceptance-criteria scenario, driven through the pages with
self.client, like a real user. See the PB-10 low-level design, Parts 5-6.

Pages:
    P12 /office-hours/propose/   URL name "propose_office_hours"
    P11 /office-hours/           URL name "my_office_hours"
"""
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from OfficeHourSchedulingApp import services
from OfficeHourSchedulingApp.models import (
    Course,
    OfficeHour,
    Section,
    SectionMeeting,
    StaffAssignment,
)

PASSWORD = "A-strong-test-password-42!"
LINK = "https://uwm.zoom.us/j/123456789"


def local_dt(day, hour, minute=0):
    """An aware datetime in the project time zone."""
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def next_weekday(weekday, at_least_days=7):
    """First date at least `at_least_days` from today on `weekday` (0 = Monday)."""
    day = timezone.localdate() + timedelta(days=at_least_days)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day


class PB10AcceptanceBase(TestCase):
    def setUp(self):
        users = get_user_model().objects
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in ("Instructor", "TA", "Student")}

        self.ta = users.create_user(email="ta@example.test", password=PASSWORD)
        self.ta.groups.add(groups["TA"])
        self.instructor = users.create_user(email="prof@example.test", password=PASSWORD)
        self.instructor.groups.add(groups["Instructor"])
        self.student = users.create_user(email="student@example.test", password=PASSWORD)
        self.student.groups.add(groups["Student"])
        self.admin = users.create_superuser(email="admin@example.test", password=PASSWORD)

        self.cs361 = Course.objects.create(number="CS361", name="Software Engineering")
        self.cs351 = Course.objects.create(number="CS351", name="Data Structures")
        self.cs361_lab = Section.objects.create(course=self.cs361, number="801", kind="LAB")
        StaffAssignment.objects.create(staff=self.ta, section=self.cs361_lab)
        StaffAssignment.objects.create(staff=self.instructor, section=self.cs361_lab)

        self.propose_url = reverse("propose_office_hours")
        self.list_url = reverse("my_office_hours")
        self.day = next_weekday(2)  # a Wednesday a week or more away

    def submit(self, start, end, course=None, link=LINK):
        """Fill in and submit the propose form as the logged-in user."""
        return self.client.post(
            self.propose_url,
            {
                "course": (course or self.cs361).pk,
                "starts_at": timezone.localtime(start).strftime("%Y-%m-%dT%H:%M"),
                "ends_at": timezone.localtime(end).strftime("%Y-%m-%dT%H:%M"),
                "meeting_url": link,
            },
            follow=True,
        )

    def assertNotAccepted(self, response, message):
        """The form came back with the message and nothing new was saved."""
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [])
        self.assertFalse(OfficeHour.objects.filter(staff=self.ta).exists())
        self.assertContains(response, message)


class ProposeOfficeHoursScenarios(PB10AcceptanceBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.ta)

    def test_successfully_propose_office_hours(self):
        """Given the staff member is logged in and assigned to the course,
        when they enter valid office-hour information and submit,
        then the proposal is stored and available for instructor approval."""
        response = self.submit(local_dt(self.day, 13), local_dt(self.day, 14))

        self.assertRedirects(response, self.list_url)
        hour = OfficeHour.objects.get()
        self.assertEqual(hour.staff, self.ta)
        self.assertEqual(hour.course, self.cs361)
        self.assertEqual(hour.starts_at, local_dt(self.day, 13))
        self.assertEqual(hour.ends_at, local_dt(self.day, 14))
        self.assertEqual(hour.meeting_url, LINK)
        self.assertEqual(hour.status, OfficeHour.Status.PENDING)  # waiting for approval
        self.assertIsNone(hour.reviewer)
        self.assertContains(response, "Pending")
        self.assertContains(response, "CS361")

    def test_unassigned_course(self):
        """Given the staff member is not assigned to the selected course,
        when they propose office hours for it, then the proposal is not accepted."""
        response = self.submit(local_dt(self.day, 13), local_dt(self.day, 14), course=self.cs351)
        self.assertNotAccepted(response, "Select a valid choice")

    def test_unassigned_course_is_not_offered(self):
        response = self.client.get(self.propose_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CS361")
        self.assertNotContains(response, "CS351")

    def test_conflicting_office_hours(self):
        """Given the staff member already has office hours scheduled,
        when they propose overlapping office hours, then the proposal is not
        accepted and they are informed of the scheduling conflict."""
        OfficeHour.objects.create(
            staff=self.ta,
            course=self.cs361,
            starts_at=local_dt(self.day, 13),
            ends_at=local_dt(self.day, 14),
            meeting_url=LINK,
            status=OfficeHour.Status.APPROVED,
        )

        response = self.submit(local_dt(self.day, 13, 30), local_dt(self.day, 14, 30))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(OfficeHour.objects.count(), 1)
        self.assertContains(response, services.MSG_CONFLICT)

    def test_end_time_before_start_time(self):
        response = self.submit(local_dt(self.day, 14), local_dt(self.day, 13))
        self.assertNotAccepted(response, services.MSG_END_BEFORE_START)

    def test_end_time_equal_to_start_time(self):
        response = self.submit(local_dt(self.day, 13), local_dt(self.day, 13))
        self.assertNotAccepted(response, services.MSG_END_BEFORE_START)

    def test_proposal_in_the_past(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        response = self.submit(local_dt(yesterday, 13), local_dt(yesterday, 14))
        self.assertNotAccepted(response, services.MSG_IN_PAST)

    def test_length_not_a_multiple_of_15_minutes(self):
        response = self.submit(local_dt(self.day, 13), local_dt(self.day, 13, 50))
        self.assertNotAccepted(response, services.MSG_NOT_MULTIPLE_OF_15)

    def test_times_not_on_a_quarter_hour(self):
        response = self.submit(local_dt(self.day, 13, 10), local_dt(self.day, 14, 10))
        self.assertNotAccepted(response, services.MSG_NOT_QUARTER_HOUR)

    def test_missing_meeting_link(self):
        response = self.submit(local_dt(self.day, 13), local_dt(self.day, 14), link="")
        self.assertNotAccepted(response, services.MSG_BAD_LINK)

    def test_link_that_does_not_start_with_https(self):
        for link in ("http://uwm.zoom.us/j/123", "uwm.zoom.us/j/123"):
            with self.subTest(link=link):
                response = self.submit(local_dt(self.day, 13), local_dt(self.day, 14), link=link)
                self.assertNotAccepted(response, services.MSG_BAD_LINK)

    def test_non_teams_or_zoom_link(self):
        response = self.submit(
            local_dt(self.day, 13), local_dt(self.day, 14), link="https://meet.google.com/abc-defg-hij"
        )
        self.assertNotAccepted(response, services.MSG_BAD_LINK)

    def test_school_zoom_and_teams_links_are_accepted(self):
        links = ("https://uwm.zoom.us/j/123456789", "https://teams.microsoft.com/l/meetup-join/abc")
        for i, link in enumerate(links):
            with self.subTest(link=link):
                start = local_dt(self.day + timedelta(days=i), 13)
                response = self.submit(start, start + timedelta(hours=1), link=link)
                self.assertRedirects(response, self.list_url)
                self.assertTrue(OfficeHour.objects.filter(meeting_url=link).exists())

    def test_conflict_with_an_assigned_section_meeting(self):
        """Given the staff member is assigned to a lab that meets Tuesdays 2:00-3:50 PM,
        when they propose office hours on a Tuesday from 3:00-4:00 PM,
        then the proposal is not accepted and they are informed of the conflict."""
        tuesday = next_weekday(1)
        SectionMeeting.objects.create(
            section=self.cs361_lab,
            weekday=1,
            start_time=time(14, 0),
            end_time=time(15, 50),
            valid_from=tuesday - timedelta(days=30),
            valid_until=tuesday + timedelta(days=30),
        )

        response = self.submit(local_dt(tuesday, 15), local_dt(tuesday, 16))

        self.assertNotAccepted(response, services.MSG_CONFLICT)

    def test_entered_values_are_kept_after_an_error(self):
        response = self.submit(local_dt(self.day, 13, 10), local_dt(self.day, 14, 10))
        self.assertContains(response, LINK)


class MyOfficeHoursPage(PB10AcceptanceBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.ta)

    def test_empty_list_shows_a_message(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You haven't proposed any office hours yet.")

    def test_lists_only_my_proposals_with_status(self):
        OfficeHour.objects.create(
            staff=self.ta,
            course=self.cs361,
            starts_at=local_dt(self.day, 13),
            ends_at=local_dt(self.day, 14),
            meeting_url=LINK,
            status=OfficeHour.Status.REJECTED,
            review_note="Please pick an afternoon slot.",
        )
        OfficeHour.objects.create(
            staff=self.instructor,
            course=self.cs361,
            starts_at=local_dt(self.day, 9),
            ends_at=local_dt(self.day, 10),
            meeting_url="https://zoom.us/j/999",
        )

        response = self.client.get(self.list_url)

        self.assertContains(response, "Rejected")
        self.assertContains(response, "Please pick an afternoon slot.")
        self.assertNotContains(response, "https://zoom.us/j/999")

    def test_page_links_to_the_propose_form(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, self.propose_url)


class ProposeOfficeHoursAccess(PB10AcceptanceBase):
    def test_instructor_can_propose(self):
        self.client.force_login(self.instructor)
        self.assertEqual(self.client.get(self.propose_url).status_code, 200)
        response = self.submit(local_dt(self.day, 13), local_dt(self.day, 14))
        self.assertRedirects(response, self.list_url)
        self.assertTrue(OfficeHour.objects.filter(staff=self.instructor).exists())

    def test_student_is_denied(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.propose_url).status_code, 403)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        response = self.submit(local_dt(self.day, 13), local_dt(self.day, 14))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(OfficeHour.objects.exists())

    def test_administrator_is_denied(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.propose_url).status_code, 403)
        response = self.submit(local_dt(self.day, 13), local_dt(self.day, 14))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(OfficeHour.objects.exists())

    def test_anonymous_user_is_redirected_to_login(self):
        for url in (self.propose_url, self.list_url):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("login", response["Location"])
        self.client.post(self.propose_url, {"course": self.cs361.pk})
        self.assertFalse(OfficeHour.objects.exists())
