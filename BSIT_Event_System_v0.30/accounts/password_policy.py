"""Password rules shared by Django forms and the browser's strength guidance."""

import re
from importlib import import_module
from threading import Lock

from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_variables

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 16
# An unpredictable eight-character password can reach Fair on the estimator's scale.
# Keep Weak and Very weak passwords blocked while allowing the requested lower boundary.
PASSWORD_MIN_SCORE = 2
PASSWORD_SCORE_LABELS = ("Very weak", "Weak", "Fair", "Strong", "Very strong")
APPLICATION_WORDS = ("bsit", "events", "student", "organizer")
_estimator_lock = Lock()


def password_user_inputs(user=None):
    """Treat account details and the application name as predictable words."""
    words = set(APPLICATION_WORDS)
    if user is not None:
        for field in ("username", "first_name", "last_name", "email"):
            value = str(getattr(user, field, "") or "").lower()
            if value:
                words.add(value)
                words.update(
                    part for part in re.split(r"[\W_]+", value) if len(part) >= 3
                )
    return sorted(words)


class GuessablePasswordValidator:
    """Reject predictable passwords before Django hashes and saves them."""

    @sensitive_variables("password")
    def validate(self, password, user=None):
        if len(password) > PASSWORD_MAX_LENGTH:
            raise ValidationError(
                "Use no more than %(maximum)s characters.",
                code="password_too_long",
                params={"maximum": PASSWORD_MAX_LENGTH},
            )
        if len(password) < PASSWORD_MIN_LENGTH:
            # Django's minimum-length validator supplies the error for short values.
            return

        # Loading settings and running migrations do not require the estimator.
        # Password changes still fail closed if its dependency has not been installed.
        try:
            estimator = import_module("zxcvbn").zxcvbn
        except ModuleNotFoundError as exc:
            if exc.name != "zxcvbn":
                raise
            raise ValidationError(
                "Password strength checking is unavailable. Install the project "
                "requirements and try again.",
                code="password_checker_unavailable",
            ) from exc

        # The estimator shares a dictionary internally. Keep account-specific inputs
        # isolated when several requests validate passwords at the same time.
        with _estimator_lock:
            score = estimator(
                password,
                user_inputs=password_user_inputs(user),
                max_length=PASSWORD_MAX_LENGTH,
            )["score"]
        if score < PASSWORD_MIN_SCORE:
            raise ValidationError(
                "This password is too easy to guess. Use a unique password "
                "and avoid names, School IDs, common passwords, and repeated patterns.",
                code="password_too_guessable",
            )
        if user is not None and user.pk and check_password(password, user.password):
            raise ValidationError(
                "Choose a password different from the current password.",
                code="password_reused",
            )

    def get_help_text(self):
        return (
            f"Use no more than {PASSWORD_MAX_LENGTH} characters and choose a password rated "
            f"{PASSWORD_SCORE_LABELS[PASSWORD_MIN_SCORE]} or better. "
            "Avoid predictable patterns and your current password."
        )
