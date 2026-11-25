"""Keep new-password guidance consistent across registration, recovery, and admin forms."""

import json

from django.contrib.auth import password_validation
from django.contrib.auth.forms import (
    AdminPasswordChangeForm,
    AdminUserCreationForm,
    PasswordChangeForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.validators import MaxLengthValidator

from .password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PASSWORD_MIN_SCORE,
    password_user_inputs,
)


class PasswordGuidanceMixin:
    password_fields = ("new_password1", "new_password2")
    password_guidance = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        primary_name, confirm_name = self.password_fields
        primary = self.fields[primary_name]
        confirmation = self.fields[confirm_name]
        if (
            "usable_password" in self.fields
            and self.is_bound
            and self.data.get(self.add_prefix("usable_password")) == "false"
        ):
            # Django's separate "disable password" action does not set a new password.
            primary.disabled = confirmation.disabled = True
        account = getattr(self, "user", None) or getattr(self, "instance", None)
        policy = {
            "minLength": PASSWORD_MIN_LENGTH,
            "maxLength": PASSWORD_MAX_LENGTH,
            "minScore": PASSWORD_MIN_SCORE,
            "userInputs": password_user_inputs(account),
        }
        primary.widget.attrs.update(
            {
                "data-password-strength": "",
                "data-password-confirm-field": self.add_prefix(confirm_name),
                "data-password-policy": json.dumps(policy),
                "minlength": PASSWORD_MIN_LENGTH,
            }
        )
        primary.help_text = password_validation.password_validators_help_text_html()
        confirmation.widget.attrs["data-password-confirmation"] = ""
        for field in (primary, confirmation):
            # Keep passphrase whitespace unchanged and bound expensive strength estimation.
            field.strip = False
            field.validators.append(MaxLengthValidator(PASSWORD_MAX_LENGTH))
            field.widget.attrs.update(
                {
                    "autocomplete": "new-password",
                    "autocapitalize": "none",
                    "spellcheck": "false",
                }
            )


class GuidedSetPasswordForm(PasswordGuidanceMixin, SetPasswordForm):
    pass


class GuidedPasswordChangeForm(PasswordGuidanceMixin, PasswordChangeForm):
    pass


class GuidedUserCreationForm(PasswordGuidanceMixin, UserCreationForm):
    password_fields = ("password1", "password2")


class GuidedAdminUserCreationForm(PasswordGuidanceMixin, AdminUserCreationForm):
    password_fields = ("password1", "password2")


class GuidedAdminPasswordChangeForm(PasswordGuidanceMixin, AdminPasswordChangeForm):
    password_fields = ("password1", "password2")
