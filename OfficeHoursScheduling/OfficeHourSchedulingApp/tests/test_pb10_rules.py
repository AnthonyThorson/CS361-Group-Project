"""PB-10 unit tests: time and meeting-link rules.

These rules are plain functions in services.py and need no database, so they
use SimpleTestCase. See the PB-10 low-level design, Part 2.
"""
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone

from OfficeHourSchedulingApp import services


def at(hour, minute=0, second=0, day=1):
    """An aware datetime on 2030-07-<day> in the project time zone."""
    return timezone.make_aware(datetime(2030, 7, day, hour, minute, second))


NOW = at(9)  # a fixed "current time" so tests never depend on the real clock


class RuleTestCase(SimpleTestCase):
    def assertRejected(self, message, func, *args):
        with self.assertRaises(ValidationError) as caught:
            func(*args)
        self.assertIn(message, caught.exception.messages)


class EndAfterStartTests(RuleTestCase):
    def test_end_after_start_passes(self):
        services.validate_end_after_start(at(13), at(14))

    def test_end_before_start_is_rejected(self):
        self.assertRejected(
            services.MSG_END_BEFORE_START, services.validate_end_after_start, at(14), at(13)
        )

    def test_end_equal_to_start_is_rejected(self):
        self.assertRejected(
            services.MSG_END_BEFORE_START, services.validate_end_after_start, at(13), at(13)
        )


class InFutureTests(RuleTestCase):
    def test_future_start_passes(self):
        services.validate_in_future(at(13), NOW)

    def test_past_start_is_rejected(self):
        self.assertRejected(services.MSG_IN_PAST, services.validate_in_future, at(8), NOW)

    def test_start_exactly_now_is_rejected(self):
        self.assertRejected(services.MSG_IN_PAST, services.validate_in_future, NOW, NOW)

    def test_yesterday_is_rejected(self):
        self.assertRejected(
            services.MSG_IN_PAST, services.validate_in_future, NOW - timedelta(days=1), NOW
        )


class LengthMultipleOf15Tests(RuleTestCase):
    def test_15_minutes_passes(self):
        services.validate_length_multiple_of_15(at(13), at(13, 15))

    def test_45_minutes_passes(self):
        services.validate_length_multiple_of_15(at(13), at(13, 45))

    def test_2_hours_passes(self):
        services.validate_length_multiple_of_15(at(13), at(15))

    def test_50_minutes_is_rejected(self):
        self.assertRejected(
            services.MSG_NOT_MULTIPLE_OF_15,
            services.validate_length_multiple_of_15,
            at(13),
            at(13, 50),
        )

    def test_10_minutes_is_rejected(self):
        self.assertRejected(
            services.MSG_NOT_MULTIPLE_OF_15,
            services.validate_length_multiple_of_15,
            at(13),
            at(13, 10),
        )

    def test_reversed_times_are_left_to_the_end_after_start_rule(self):
        # The design says this rule is skipped when end <= start.
        services.validate_length_multiple_of_15(at(14), at(13, 50))


class QuarterHourTests(RuleTestCase):
    def test_all_quarter_hours_pass(self):
        for minute in (0, 15, 30, 45):
            with self.subTest(minute=minute):
                services.validate_quarter_hour(at(13, minute), at(15, minute))

    def test_start_at_1_10_pm_is_rejected(self):
        self.assertRejected(
            services.MSG_NOT_QUARTER_HOUR, services.validate_quarter_hour, at(13, 10), at(14, 10)
        )

    def test_end_off_the_quarter_hour_is_rejected(self):
        self.assertRejected(
            services.MSG_NOT_QUARTER_HOUR, services.validate_quarter_hour, at(13), at(13, 50)
        )

    def test_seconds_are_rejected(self):
        self.assertRejected(
            services.MSG_NOT_QUARTER_HOUR, services.validate_quarter_hour, at(13, 0, 30), at(14)
        )


class MeetingUrlTests(RuleTestCase):
    def test_accepted_links(self):
        for url in (
            "https://zoom.us/j/123456789",
            "https://uwm.zoom.us/j/123456789",
            "https://UWM.Zoom.us/j/123456789",
            "https://teams.microsoft.com/l/meetup-join/abc",
            "https://teams.live.com/meet/123",
        ):
            with self.subTest(url=url):
                services.validate_meeting_url(url)

    def test_missing_link_is_rejected(self):
        for url in ("", "   ", None):
            with self.subTest(url=url):
                self.assertRejected(services.MSG_BAD_LINK, services.validate_meeting_url, url)

    def test_link_without_https_is_rejected(self):
        for url in (
            "http://uwm.zoom.us/j/123",
            "uwm.zoom.us/j/123",
            "ftp://zoom.us/j/123",
        ):
            with self.subTest(url=url):
                self.assertRejected(services.MSG_BAD_LINK, services.validate_meeting_url, url)

    def test_other_meeting_services_are_rejected(self):
        for url in (
            "https://meet.google.com/abc-defg-hij",
            "https://example.com/meeting",
            "https://webex.com/meet/123",
        ):
            with self.subTest(url=url):
                self.assertRejected(services.MSG_BAD_LINK, services.validate_meeting_url, url)

    def test_lookalike_hosts_are_rejected(self):
        for url in (
            "https://zoom.us.evil.com/j/123",
            "https://notzoom.us/j/123",
            "https://evil.com/zoom.us",
            "https://teams.microsoft.com.evil.com/meet",
            "https://fakezoom.us@evil.com/j/123",
        ):
            with self.subTest(url=url):
                self.assertRejected(services.MSG_BAD_LINK, services.validate_meeting_url, url)
