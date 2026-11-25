"""Short-lived, session-bound reviews of students identified by a rotating QR."""

import hashlib
import json
import secrets
import time

from django.core import signing
from django.utils import timezone
from django.utils.dateparse import parse_datetime

REVIEW_SECONDS = 60
REVIEW_SALT = "bsit.attendance.identity-review.v1"
SESSION_KEY = "attendance_identity_reviews"
SCAN_LABELS = {"IN": "Time In", "OUT": "Time Out", "EXCUSED_OUT": "Excused Time Out"}


def student_identity(profile):
    return {
        "name": profile.display_name,
        "school_id": profile.student_id or profile.user.username,
        "program": profile.program,
        "year_section": profile.year_level,
        "photo_url": profile.profile_image.url if profile.profile_image else "",
    }


def _fingerprint(value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def identity_fingerprint(profile):
    identity = student_identity(profile)
    # Use the stored path so expiring storage URLs cannot invalidate an unchanged photo.
    identity["photo_url"] = profile.profile_image.name or ""
    return _fingerprint(identity)


def attendance_fingerprint(record):
    if record is None:
        return _fingerprint(None)
    return _fingerprint(
        [
            record.pk,
            record.in_at.isoformat() if record.in_at else None,
            record.out_at.isoformat() if record.out_at else None,
            record.excused_time_out,
        ]
    )


def schedule_fingerprint(event):
    return _fingerprint(
        [
            event.date.isoformat(),
            event.end_date.isoformat() if event.end_date else None,
            event.start_time.isoformat(),
            event.end_time.isoformat(),
            event.organizer_id,
            event.status == event.Status.CANCELLED,
            event.early_time_out_until.isoformat() if event.early_time_out_until else None,
        ]
    )


def create_review(request, event, profile, record, session, scan_type, scanned_at):
    nonce = secrets.token_urlsafe(24)
    now = time.time()
    reviews = {
        key: value
        for key, value in request.session.get(SESSION_KEY, {}).items()
        if value.get("expires_at", 0) > now
    }
    # Keep one current review per event and bound reviews in other open scanner tabs.
    while len(reviews) >= 8:
        reviews.pop(next(iter(reviews)))
    expires_at = int(now) + REVIEW_SECONDS
    reviews[str(event.pk)] = {"nonce": nonce, "expires_at": expires_at}
    request.session[SESSION_KEY] = reviews
    payload = {
        "nonce": nonce,
        "organizer": request.user.pk,
        "event": event.pk,
        "student": profile.user_id,
        "day": session.day.isoformat(),
        "scan_type": scan_type,
        "scanned_at": scanned_at.isoformat(),
        "identity": identity_fingerprint(profile),
        "attendance": attendance_fingerprint(record),
        "schedule": schedule_fingerprint(event),
    }
    return signing.dumps(payload, salt=REVIEW_SALT, compress=True), expires_at


def read_review(request, event, token):
    if not token or len(token) > 4096:
        return None, "Scan the student's QR and confirm their identity before recording attendance."
    try:
        payload = signing.loads(token, salt=REVIEW_SALT, max_age=REVIEW_SECONDS)
        if not isinstance(payload, dict):
            raise ValueError
        review = request.session.get(SESSION_KEY, {}).get(str(event.pk), {})
        if (
            payload.get("organizer") != request.user.pk
            or payload.get("event") != event.pk
            or payload.get("nonce") != review.get("nonce")
            or review.get("expires_at", 0) <= time.time()
        ):
            raise ValueError
        scanned_at = parse_datetime(payload["scanned_at"])
        if scanned_at is None or timezone.is_naive(scanned_at) or scanned_at > timezone.now():
            raise ValueError
        payload["observed_at"] = scanned_at
        return payload, None
    except (signing.BadSignature, ValueError, KeyError, TypeError):
        return (
            None,
            "This confirmation expired, was cancelled, or was replaced. Scan the latest QR again.",
        )


def discard_review(request, event, token):
    # A delayed Cancel must never discard a newer review from another scanner tab.
    try:
        payload = signing.loads(token, salt=REVIEW_SALT)
        reviews = dict(request.session.get(SESSION_KEY, {}))
        current = reviews.get(str(event.pk), {})
        if (
            payload.get("organizer") == request.user.pk
            and payload.get("event") == event.pk
            and payload.get("nonce") == current.get("nonce")
        ):
            reviews.pop(str(event.pk), None)
            request.session[SESSION_KEY] = reviews
    except (signing.BadSignature, ValueError, TypeError, AttributeError):
        pass
