from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from attendance.models import Attendance
from events.models import Event


class StudentDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="024A-TEST031")
        cls.profile = Profile.objects.create(
            user=cls.user,
            role=Profile.Role.STUDENT,
            student_id=cls.user.username,
            must_change_password=False,
        )
        cls.day = date(2026, 11, 24)
        cls.now = datetime(2026, 11, 24, 10, tzinfo=ZoneInfo("Asia/Manila"))

    def setUp(self):
        self.client.force_login(self.user)
        clock = patch("django.utils.timezone.now", return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def test_history_reaches_older_events_and_their_scans(self):
        events = [
            Event.objects.create(
                name=f"Past event {offset}",
                date=self.day - timedelta(days=offset),
                start_time=time(8),
                end_time=time(17),
                venue="Campus",
                status=Event.Status.COMPLETED,
            )
            for offset in range(1, 22)
        ]
        oldest = events[-1]
        Attendance.objects.create(
            student=self.profile,
            event=oldest,
            in_at=oldest.starts_at,
            out_at=oldest.ends_at,
        )
        first = self.client.get(reverse("stamps:student_history_page"))
        self.assertEqual(first.status_code, 200)
        self.assertIsNotNone(first.context.get("history_page"))
        self.assertTrue(first.context["history_page"].has_next())
        second = self.client.get(reverse("stamps:student_history_page"), {"page": 2})
        self.assertContains(second, oldest.name)
        item = next(item for item in second.context["event_history"] if item["event"] == oldest)
        self.assertEqual(item["status"], "ATTENDED")
        self.assertEqual(len(item["daily_records"]), 1)

    def test_qr_prioritizes_the_students_checked_in_event(self):
        earlier = Event.objects.create(
            name="Another ongoing event",
            date=self.day,
            start_time=time(8),
            end_time=time(17),
            venue="Hall A",
        )
        checked_in = Event.objects.create(
            name="The student's current event",
            date=self.day,
            start_time=time(9),
            end_time=time(17),
            venue="Hall B",
        )
        Attendance.objects.create(
            student=self.profile, event=checked_in, in_at=checked_in.starts_at
        )
        response = self.client.get(reverse("stamps:student_qr_page"))
        self.assertEqual(response.context["active_event"], checked_in)
        self.assertNotEqual(response.context["active_event"], earlier)
