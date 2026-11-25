from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from administration.models import ActivityLog
from events.models import Event
from stamps.models import EventStamp

from .models import Attendance
from .services import create_qr_token, qr_token_expiry, validate_qr_token


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class IdentityReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.day = date(2026, 11, 24)
        cls.zone = ZoneInfo("Asia/Manila")
        cls.organizer = User.objects.create_user("qr-review-organizer")
        cls.other_organizer = User.objects.create_user("qr-review-other-organizer")
        for user in (cls.organizer, cls.other_organizer):
            Profile.objects.create(user=user, role=Profile.Role.ORGANIZER)
            Profile.objects.filter(user=user).update(must_change_password=False)
        cls.student = User.objects.create_user(
            "024A-034001", first_name="Clara", last_name="Ellison"
        )
        cls.profile = Profile.objects.create(
            user=cls.student,
            role=Profile.Role.STUDENT,
            student_id=cls.student.username,
            program="BSIT",
            year_level="2A",
        )
        cls.other_student = User.objects.create_user("024A-034002")
        cls.other_profile = Profile.objects.create(
            user=cls.other_student, role=Profile.Role.STUDENT, student_id=cls.other_student.username
        )
        cls.event = Event.objects.create(
            name="QR identity review",
            date=cls.day,
            start_time=time(8),
            end_time=time(17),
            organizer=cls.organizer,
            venue="Campus hall",
            stamps_per_student=1,
        )

    def setUp(self):
        self.moment = datetime(2026, 11, 24, 10, tzinfo=self.zone)
        for target, value in (
            ("django.utils.timezone.now", lambda: self.moment),
            ("time.time", lambda: self.moment.timestamp()),
        ):
            clock = patch(target, side_effect=value)
            clock.start()
            self.addCleanup(clock.stop)
        self.client.force_login(self.organizer)

    def at(self, hour, minute=0, second=0, offset=0):
        self.moment = datetime.combine(
            self.day + timedelta(days=offset), time(hour, minute, second), self.zone
        )

    def preview(self, mode="IN", *, client=None, token=None, event=None, expected=200):
        target = event or self.event
        response = (client or self.client).post(
            reverse("attendance:scan_preview", args=(target.pk,)),
            {
                "token": token or create_qr_token(self.profile),
                "scan_type": mode,
                "day": target.attendance_date_at(self.moment).isoformat(),
            },
        )
        self.assertEqual(response.status_code, expected, response.content[:300])
        return response.json()

    def confirm(self, review, *, client=None, event=None, expected=200, **overrides):
        data = {
            "confirmation": review["confirmation"],
            "identity_confirmed": "1",
            "day": review["day"],
            "scan_type": review["scan_type"],
            **overrides,
        }
        response = (client or self.client).post(
            reverse("attendance:scan_api", args=((event or self.event).pk,)), data
        )
        self.assertEqual(response.status_code, expected, response.content[:300])
        return response.json()

    def test_preview_shows_the_qr_owners_details_and_writes_no_attendance(self):
        review = self.preview()
        self.assertEqual(review["student"]["name"], "Clara Ellison")
        self.assertEqual(review["student"]["school_id"], self.student.username)
        self.assertEqual(review["student"]["program"], "BSIT")
        self.assertEqual(review["student"]["year_section"], "2A")
        self.assertEqual(review["student"]["photo_url"], "")
        self.assertTrue(review["requires_confirmation"])
        self.assertFalse(Attendance.objects.exists())
        self.assertFalse(EventStamp.objects.exists())
        self.assertFalse(ActivityLog.objects.exists())

    def test_confirm_is_required_and_records_the_original_scan_time(self):
        review = self.preview()
        self.confirm(review, identity_confirmed="0", expected=400)
        self.assertFalse(Attendance.objects.exists())
        observed = self.moment
        self.moment += timedelta(seconds=5)
        self.confirm(review)
        record = Attendance.objects.get()
        self.assertEqual(record.in_at, observed)
        self.assertEqual(record.in_scanned_by_id, self.organizer.pk)
        self.assertIn("identity visually confirmed", ActivityLog.objects.get().details.lower())

    def test_identity_and_attendance_belong_to_the_scanned_student(self):
        review = self.preview(token=create_qr_token(self.other_profile))
        self.assertEqual(review["student"]["school_id"], self.other_student.username)
        self.confirm(review, student_id=self.profile.student_id)
        self.assertEqual(Attendance.objects.get().student_id, self.other_profile.pk)

    def test_raw_qr_cannot_bypass_confirmation(self):
        response = self.client.post(
            reverse("attendance:scan_api", args=(self.event.pk,)),
            {"token": create_qr_token(self.profile), "scan_type": "IN", "identity_confirmed": "1"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Attendance.objects.exists())

    def test_reject_records_nothing_and_invalidates_the_review(self):
        review = self.preview()
        response = self.client.post(
            reverse("attendance:scan_preview", args=(self.event.pk,)),
            {"action": "reject", "confirmation": review["confirmation"]},
        )
        self.assertTrue(response.json()["ok"])
        self.confirm(review, expected=409)
        self.assertFalse(Attendance.objects.exists())
        self.assertFalse(EventStamp.objects.exists())

    def test_original_qr_may_rotate_during_review(self):
        token = create_qr_token(self.profile)
        observed = self.moment
        review = self.preview(token=token)
        self.moment += timedelta(seconds=26)
        self.assertNotEqual(create_qr_token(self.profile), token)
        self.assertIsNotNone(validate_qr_token(token)[1])
        self.confirm(review)
        self.assertEqual(Attendance.objects.get().in_at, observed)

    def test_expired_qr_cannot_start_a_review(self):
        token = create_qr_token(self.profile)
        self.moment = datetime.fromtimestamp(qr_token_expiry(token) + 0.01, self.zone)
        result = self.preview(token=token, expected=400)
        self.assertIn("expired", result["message"])
        self.assertFalse(Attendance.objects.exists())

    def test_expired_review_cannot_save_attendance(self):
        review = self.preview()
        self.moment += timedelta(seconds=61)
        self.confirm(review, expected=409)
        self.assertFalse(Attendance.objects.exists())

    def test_signature_mode_and_day_tampering_are_rejected(self):
        review = self.preview()
        self.confirm(review, scan_type="OUT", expected=409)
        self.confirm(review, day=(self.day + timedelta(days=1)).isoformat(), expected=409)
        self.confirm(review, confirmation=review["confirmation"] + "x", expected=409)
        self.assertFalse(Attendance.objects.exists())

    def test_other_organizers_and_students_cannot_view_the_identity(self):
        for user in (self.other_organizer, self.student):
            client = Client()
            client.force_login(user)
            result = self.preview(client=client, expected=403)
            self.assertNotIn("student", result)

    def test_review_is_bound_to_the_login_session(self):
        review = self.preview()
        another_session = Client()
        another_session.force_login(self.organizer)
        self.confirm(review, client=another_session, expected=409)
        self.assertFalse(Attendance.objects.exists())

    def test_review_cannot_be_used_for_another_event(self):
        review = self.preview()
        other_event = Event.objects.create(
            name="Another event",
            date=self.day,
            start_time=time(8),
            end_time=time(17),
            organizer=self.organizer,
            venue="Hall B",
        )
        self.confirm(review, event=other_event, expected=409)
        self.assertFalse(Attendance.objects.exists())
        self.confirm(review)

    def test_overnight_review_keeps_the_day_that_the_session_started(self):
        event = Event.objects.create(
            name="Overnight event",
            date=self.day,
            start_time=time(22),
            end_time=time(6),
            organizer=self.organizer,
            venue="Hall",
        )
        self.at(23, 59, 59)
        review = self.preview(event=event)
        self.moment += timedelta(seconds=2)
        self.confirm(review, event=event)
        self.assertEqual(Attendance.objects.get().attendance_date, self.day)

    def test_old_review_and_delayed_cancel_do_not_replace_new_review(self):
        older = self.preview()
        newer = self.preview()
        self.confirm(older, expected=409)
        self.client.post(
            reverse("attendance:scan_preview", args=(self.event.pk,)),
            {"action": "reject", "confirmation": older["confirmation"]},
        )
        self.confirm(newer)
        self.assertEqual(Attendance.objects.count(), 1)

    def test_confirmed_review_cannot_be_replayed_even_after_a_record_is_deleted(self):
        review = self.preview()
        self.confirm(review)
        self.confirm(review, expected=409)
        Attendance.objects.all().delete()
        self.confirm(review, expected=409)
        self.assertFalse(Attendance.objects.exists())

    def test_identity_schedule_and_attendance_changes_require_a_new_review(self):
        review = self.preview()
        Profile.objects.filter(pk=self.profile.pk).update(profile_image="profiles/new-photo.jpg")
        self.confirm(review, expected=409)
        Profile.objects.filter(pk=self.profile.pk).update(profile_image="")
        review = self.preview()
        Event.objects.filter(pk=self.event.pk).update(end_time=time(18))
        self.confirm(review, expected=409)
        Event.objects.filter(pk=self.event.pk).update(end_time=time(17))
        review = self.preview()
        Attendance.objects.create(student=self.profile, event=self.event, in_at=self.moment)
        self.confirm(review, expected=409)
        self.assertEqual(Attendance.objects.count(), 1)

    def test_inactive_student_and_reassigned_event_cannot_be_confirmed(self):
        review = self.preview()
        User.objects.filter(pk=self.student.pk).update(is_active=False)
        self.confirm(review, expected=404)
        User.objects.filter(pk=self.student.pk).update(is_active=True)
        review = self.preview()
        Event.objects.filter(pk=self.event.pk).update(organizer=self.other_organizer)
        self.confirm(review, expected=403)
        self.assertFalse(Attendance.objects.exists())

    def test_duplicate_and_early_checkout_checks_still_apply(self):
        self.preview("OUT", expected=403)
        self.confirm(self.preview())
        self.preview(expected=409)
        self.preview("OUT", expected=403)
        self.at(16, 56)
        self.confirm(self.preview("OUT"))
        self.preview("OUT", expected=409)
        self.assertEqual(Attendance.objects.count(), 1)
        self.assertEqual(EventStamp.objects.get().quantity, 1)

    def test_excused_checkout_and_late_checkout_still_award_stamps(self):
        self.confirm(self.preview())
        self.moment += timedelta(minutes=1)
        self.confirm(self.preview("EXCUSED_OUT"))
        self.assertEqual(Attendance.objects.get().status, "EXCUSED")
        self.assertEqual(EventStamp.objects.get().quantity, 1)
        Attendance.objects.all().delete()
        EventStamp.objects.all().delete()
        Attendance.objects.create(student=self.profile, event=self.event, in_at=self.moment)
        self.at(18)
        response = self.confirm(self.preview("OUT"))
        self.assertFalse(response["timing"]["scanning_open"])
        self.assertEqual(EventStamp.objects.get().quantity, 1)

    def test_review_can_finish_after_the_session_end_using_the_valid_scan_time(self):
        self.at(16, 59, 59)
        observed = self.moment
        review = self.preview()
        self.moment += timedelta(seconds=2)
        response = self.confirm(review)
        self.assertEqual(Attendance.objects.get().in_at, observed)
        self.assertTrue(response["timing"]["time_out_allowed"])
        self.assertFalse(response["timing"]["time_in_allowed"])

    def test_multi_day_award_requires_confirmed_scans_on_every_day(self):
        event = Event.objects.create(
            name="Three-day reviewed program",
            date=self.day,
            end_date=self.day + timedelta(days=2),
            start_time=time(8),
            end_time=time(17),
            organizer=self.organizer,
            venue="Hall",
            stamps_per_student=1,
        )
        for offset in range(3):
            self.at(10, offset=offset)
            self.confirm(self.preview(event=event), event=event)
            self.at(16, 56, offset=offset)
            self.confirm(self.preview("OUT", event=event), event=event)
            self.assertEqual(EventStamp.objects.count(), 1 if offset == 2 else 0)
        self.assertEqual(EventStamp.objects.get().quantity, 1)

    def test_csrf_is_required_for_preview_and_confirmation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.organizer)
        response = client.post(reverse("attendance:scan_preview", args=(self.event.pk,)), {})
        self.assertEqual(response.status_code, 403)
        client.get(reverse("attendance:scanner", args=(self.event.pk,)))
        csrf = client.cookies["csrftoken"].value
        response = client.post(
            reverse("attendance:scan_preview", args=(self.event.pk,)),
            {
                "token": create_qr_token(self.profile),
                "scan_type": "IN",
                "day": self.day.isoformat(),
                "csrfmiddlewaretoken": csrf,
            },
        )
        self.assertEqual(response.status_code, 200)
        review = response.json()
        response = client.post(reverse("attendance:scan_api", args=(self.event.pk,)), {})
        self.assertEqual(response.status_code, 403)
        self.confirm(review, client=client, csrfmiddlewaretoken=csrf)

    def test_qr_card_is_personal_and_its_signed_png_keeps_rotating(self):
        client = Client()
        client.force_login(self.student)
        response = client.get(reverse("stamps:student_qr_page"))
        self.assertContains(response, self.student.username)
        self.assertContains(response, "Clara Ellison")
        self.assertContains(response, "student-qr-identity")
        first = client.get(reverse("stamps:student_qr"))
        self.assertEqual(first["Content-Type"], "image/png")
        self.assertIn("no-store", first["Cache-Control"])
        self.assertGreater(float(first["X-QR-Expires-At"]), float(first["X-QR-Server-Time"]))
        self.moment += timedelta(seconds=26)
        second = client.get(reverse("stamps:student_qr"))
        self.assertNotEqual(first.content, second.content)
        self.assertNotEqual(first["X-QR-Expires-At"], second["X-QR-Expires-At"])
        self.assertNotEqual(create_qr_token(self.profile), create_qr_token(self.other_profile))
