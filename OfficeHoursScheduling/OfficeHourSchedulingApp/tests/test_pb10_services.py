"""PB-10 unit tests: course assignment, conflicts and create_proposal.

These need the database and the models (OfficeHour from PB-10; Course,
Section, SectionMeeting and StaffAssignment from PB-03 / PB-07).
See the PB-10 low-level design, Parts 1-3.
"""
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
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


class PB10ServiceTestBase(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.ta = users.create_user(email="ta@example.test", password=PASSWORD)
        self.other_ta = users.create_user(email="ta2@example.test", password=PASSWORD)

        self.cs361 = Course.objects.create(number="CS361", name="Software Engineering")
        self.cs351 = Course.objects.create(number="CS351", name="Data Structures")
        self.cs361_lab = Section.objects.create(course=self.cs361, number="801", kind="LAB")
        StaffAssignment.objects.create(staff=self.ta, section=self.cs361_lab)
        StaffAssignment.objects.create(staff=self.other_ta, section=self.cs361_lab)

        # A Wednesday a week or more away, so tests never fall in the past.
        self.day = next_weekday(2)

    def propose(self, start_hour, end_hour, course=None, staff=None, start_min=0, end_min=0):
        return services.create_proposal(
            staff=staff or self.ta,
            course=course or self.cs361,
            start=local_dt(self.day, start_hour, start_min),
            end=local_dt(self.day, end_hour, end_min),
            url=LINK,
        )

    def make_hour(self, start_hour, end_hour, status, staff=None, course=None):
        """Insert an OfficeHour directly, skipping the rules (test setup only)."""
        return OfficeHour.objects.create(
            staff=staff or self.ta,
            course=course or self.cs361,
            starts_at=local_dt(self.day, start_hour),
            ends_at=local_dt(self.day, end_hour),
            meeting_url=LINK,
            status=status,
        )


class AssignedCoursesTests(PB10ServiceTestBase):
    def test_lists_only_assigned_courses(self):
        self.assertEqual(list(services.assigned_courses(self.ta)), [self.cs361])

    def test_course_appears_once_with_several_sections(self):
        lecture = Section.objects.create(course=self.cs361, number="001", kind="LEC")
        StaffAssignment.objects.create(staff=self.ta, section=lecture)
        self.assertEqual(list(services.assigned_courses(self.ta)), [self.cs361])

    def test_unassigned_staff_has_no_courses(self):
        nobody = get_user_model().objects.create_user(email="new@example.test", password=PASSWORD)
        self.assertFalse(services.assigned_courses(nobody).exists())


class ValidateAssignedTests(PB10ServiceTestBase):
    def test_assigned_course_passes(self):
        services.validate_assigned(self.ta, self.cs361)

    def test_unassigned_course_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            services.validate_assigned(self.ta, self.cs351)
        self.assertIn(services.MSG_NOT_ASSIGNED, caught.exception.messages)


class OfficeHourConflictTests(PB10ServiceTestBase):
    """find_conflicts, part A: the staff member's own office hours."""

    def conflicts(self, start_hour, end_hour, start_min=0, end_min=0, staff=None):
        return services.find_conflicts(
            staff or self.ta,
            local_dt(self.day, start_hour, start_min),
            local_dt(self.day, end_hour, end_min),
        )

    def test_no_office_hours_means_no_conflicts(self):
        self.assertEqual(self.conflicts(13, 14), [])

    def test_overlap_with_pending_is_a_conflict(self):
        self.make_hour(13, 14, OfficeHour.Status.PENDING)
        self.assertEqual(len(self.conflicts(13, 14, start_min=30, end_min=30)), 1)

    def test_overlap_with_approved_is_a_conflict(self):
        self.make_hour(13, 14, OfficeHour.Status.APPROVED)
        self.assertEqual(len(self.conflicts(12, 15)), 1)

    def test_overlap_with_rejected_is_not_a_conflict(self):
        self.make_hour(13, 14, OfficeHour.Status.REJECTED)
        self.assertEqual(self.conflicts(13, 14), [])

    def test_proposal_inside_existing_hours_is_a_conflict(self):
        self.make_hour(12, 16, OfficeHour.Status.APPROVED)
        self.assertEqual(len(self.conflicts(13, 14)), 1)

    def test_back_to_back_before_is_not_a_conflict(self):
        self.make_hour(13, 14, OfficeHour.Status.APPROVED)
        self.assertEqual(self.conflicts(12, 13), [])

    def test_back_to_back_after_is_not_a_conflict(self):
        self.make_hour(13, 14, OfficeHour.Status.APPROVED)
        self.assertEqual(self.conflicts(14, 15), [])

    def test_overlap_in_a_different_course_is_a_conflict(self):
        self.make_hour(13, 14, OfficeHour.Status.APPROVED, course=self.cs351)
        self.assertEqual(len(self.conflicts(13, 14)), 1)

    def test_another_staff_members_hours_are_not_a_conflict(self):
        self.make_hour(13, 14, OfficeHour.Status.APPROVED, staff=self.other_ta)
        self.assertEqual(self.conflicts(13, 14), [])

    def test_same_time_on_another_day_is_not_a_conflict(self):
        OfficeHour.objects.create(
            staff=self.ta,
            course=self.cs361,
            starts_at=local_dt(self.day + timedelta(days=1), 13),
            ends_at=local_dt(self.day + timedelta(days=1), 14),
            meeting_url=LINK,
            status=OfficeHour.Status.APPROVED,
        )
        self.assertEqual(self.conflicts(13, 14), [])


class SectionMeetingConflictTests(PB10ServiceTestBase):
    """find_conflicts, part B: weekly section meetings (lab: Tuesdays 2:00-3:50 PM)."""

    def setUp(self):
        super().setUp()
        self.tuesday = next_weekday(1)
        self.lab_meeting = SectionMeeting.objects.create(
            section=self.cs361_lab,
            weekday=1,
            start_time=time(14, 0),
            end_time=time(15, 50),
            valid_from=self.tuesday - timedelta(days=30),
            valid_until=self.tuesday + timedelta(days=30),
        )

    def conflicts(self, day, start_hour, end_hour, staff=None):
        return services.find_conflicts(
            staff or self.ta, local_dt(day, start_hour), local_dt(day, end_hour)
        )

    def test_overlap_with_lab_is_a_conflict(self):
        self.assertEqual(len(self.conflicts(self.tuesday, 15, 16)), 1)

    def test_covering_the_whole_lab_is_a_conflict(self):
        self.assertEqual(len(self.conflicts(self.tuesday, 13, 17)), 1)

    def test_right_after_lab_is_not_a_conflict(self):
        self.assertEqual(self.conflicts(self.tuesday, 16, 17), [])

    def test_right_before_lab_is_not_a_conflict(self):
        self.assertEqual(self.conflicts(self.tuesday, 13, 14), [])

    def test_same_time_on_a_different_weekday_is_not_a_conflict(self):
        self.assertEqual(self.conflicts(self.tuesday + timedelta(days=1), 15, 16), [])

    def test_before_meeting_date_range_is_not_a_conflict(self):
        self.lab_meeting.valid_from = self.tuesday + timedelta(days=1)
        self.lab_meeting.save()
        self.assertEqual(self.conflicts(self.tuesday, 15, 16), [])

    def test_after_meeting_date_range_is_not_a_conflict(self):
        self.lab_meeting.valid_until = self.tuesday - timedelta(days=1)
        self.lab_meeting.save()
        self.assertEqual(self.conflicts(self.tuesday, 15, 16), [])

    def test_first_and_last_day_of_range_count(self):
        for field in ("valid_from", "valid_until"):
            with self.subTest(edge=field):
                setattr(self.lab_meeting, field, self.tuesday)
                self.lab_meeting.save()
                self.assertEqual(len(self.conflicts(self.tuesday, 15, 16)), 1)

    def test_unassigned_staff_is_not_affected_by_the_lab(self):
        nobody = get_user_model().objects.create_user(email="new@example.test", password=PASSWORD)
        self.assertEqual(self.conflicts(self.tuesday, 15, 16, staff=nobody), [])

    def test_lab_and_office_hours_conflicts_are_both_reported(self):
        OfficeHour.objects.create(
            staff=self.ta,
            course=self.cs361,
            starts_at=local_dt(self.tuesday, 15),
            ends_at=local_dt(self.tuesday, 16),
            meeting_url=LINK,
            status=OfficeHour.Status.PENDING,
        )
        self.assertEqual(len(self.conflicts(self.tuesday, 15, 16)), 2)


class CreateProposalTests(PB10ServiceTestBase):
    def assertRejected(self, message, **overrides):
        args = {
            "staff": self.ta,
            "course": self.cs361,
            "start": local_dt(self.day, 13),
            "end": local_dt(self.day, 14),
            "url": LINK,
        }
        args.update(overrides)
        with self.assertRaises(ValidationError) as caught:
            services.create_proposal(**args)
        self.assertTrue(
            any(message in m for m in caught.exception.messages),
            f"{message!r} not found in {caught.exception.messages}",
        )
        return caught.exception

    def test_valid_proposal_saved_as_pending(self):
        hour = self.propose(13, 14)

        self.assertIsInstance(hour, OfficeHour)
        self.assertEqual(OfficeHour.objects.count(), 1)
        self.assertEqual(hour.status, OfficeHour.Status.PENDING)
        self.assertEqual(hour.staff, self.ta)
        self.assertEqual(hour.course, self.cs361)
        self.assertEqual(hour.starts_at, local_dt(self.day, 13))
        self.assertEqual(hour.ends_at, local_dt(self.day, 14))
        self.assertEqual(hour.meeting_url, LINK)

    def test_new_proposal_has_no_review_yet(self):
        hour = self.propose(13, 14)
        self.assertIsNone(hour.reviewer)
        self.assertIsNone(hour.reviewed_at)
        self.assertEqual(hour.review_note, "")

    def test_45_minute_proposal_is_accepted(self):
        hour = self.propose(13, 13, end_min=45)
        self.assertEqual(hour.ends_at - hour.starts_at, timedelta(minutes=45))

    def test_back_to_back_proposals_are_accepted(self):
        self.propose(13, 14)
        self.propose(14, 15)
        self.assertEqual(OfficeHour.objects.count(), 2)

    def test_unassigned_course_is_rejected(self):
        self.assertRejected(services.MSG_NOT_ASSIGNED, course=self.cs351)
        self.assertFalse(OfficeHour.objects.exists())

    def test_end_before_start_is_rejected(self):
        self.assertRejected(
            services.MSG_END_BEFORE_START,
            start=local_dt(self.day, 14),
            end=local_dt(self.day, 13),
        )
        self.assertFalse(OfficeHour.objects.exists())

    def test_past_start_is_rejected_using_the_now_parameter(self):
        self.assertRejected(services.MSG_IN_PAST, now=local_dt(self.day, 13, 30))
        self.assertFalse(OfficeHour.objects.exists())

    def test_50_minutes_is_rejected(self):
        self.assertRejected(services.MSG_NOT_MULTIPLE_OF_15, end=local_dt(self.day, 13, 50))
        self.assertFalse(OfficeHour.objects.exists())

    def test_1_10_pm_start_is_rejected(self):
        self.assertRejected(
            services.MSG_NOT_QUARTER_HOUR,
            start=local_dt(self.day, 13, 10),
            end=local_dt(self.day, 14, 10),
        )
        self.assertFalse(OfficeHour.objects.exists())

    def test_bad_link_is_rejected(self):
        self.assertRejected(services.MSG_BAD_LINK, url="https://meet.google.com/abc-defg-hij")
        self.assertFalse(OfficeHour.objects.exists())

    def test_all_time_problems_are_reported_together(self):
        # 1:00-1:50 breaks both the 15-minute-length rule and the quarter-hour rule.
        error = self.assertRejected(services.MSG_NOT_MULTIPLE_OF_15, end=local_dt(self.day, 13, 50))
        self.assertIn(services.MSG_NOT_QUARTER_HOUR, error.messages)

    def test_conflict_is_rejected_and_nothing_new_is_saved(self):
        self.propose(13, 14)
        self.assertRejected(
            services.MSG_CONFLICT,
            start=local_dt(self.day, 13, 30),
            end=local_dt(self.day, 14, 30),
        )
        self.assertEqual(OfficeHour.objects.count(), 1)

    def test_duplicate_proposal_is_rejected(self):
        self.propose(13, 14)
        self.assertRejected(services.MSG_CONFLICT)
        self.assertEqual(OfficeHour.objects.count(), 1)

    def test_conflict_with_section_meeting_is_rejected(self):
        tuesday = next_weekday(1)
        SectionMeeting.objects.create(
            section=self.cs361_lab,
            weekday=1,
            start_time=time(14, 0),
            end_time=time(15, 50),
            valid_from=tuesday,
            valid_until=tuesday,
        )
        self.assertRejected(
            services.MSG_CONFLICT,
            start=local_dt(tuesday, 15),
            end=local_dt(tuesday, 16),
        )
        self.assertFalse(OfficeHour.objects.exists())

    def test_overlapping_a_rejected_proposal_is_allowed(self):
        self.make_hour(13, 14, OfficeHour.Status.REJECTED)
        self.propose(13, 14)
        self.assertEqual(OfficeHour.objects.count(), 2)
