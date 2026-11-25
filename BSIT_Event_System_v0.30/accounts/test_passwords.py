from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from administration.forms import ManagedAccountCreateForm, TemporaryPasswordForm

from .forms import StudentRegistrationForm
from .models import Profile
from .password_forms import (
    GuidedAdminPasswordChangeForm,
    GuidedPasswordChangeForm,
    GuidedSetPasswordForm,
)

STRONG_PASSWORD = "f8!Vz6@uQ2#rM7$x"
WEAK_PASSWORD = "Abc123!Abc123!"


class PasswordPolicyTests(SimpleTestCase):
    def test_short_common_numeric_and_predictable_passwords_are_rejected(self):
        for password in ("Sh0rt!", "passwordpassword", "123456789012345", WEAK_PASSWORD):
            with self.subTest(password_type=len(password)), self.assertRaises(ValidationError):
                validate_password(password)

    def test_acceptable_passwords_at_both_length_boundaries_are_accepted(self):
        for password in ("v8#Q2!rZ", STRONG_PASSWORD, "  f8!Vz6@uQ2  "):
            with self.subTest(length=len(password)):
                validate_password(password)

    def test_passwords_based_on_account_details_are_rejected(self):
        user = User(username="Seraphina032", first_name="Seraphina")
        with self.assertRaises(ValidationError):
            validate_password(user.username, user)

    def test_oversized_passwords_are_rejected(self):
        with self.assertRaises(ValidationError):
            validate_password(STRONG_PASSWORD + "!")

    def test_seven_character_password_is_rejected_for_its_length(self):
        with self.assertRaises(ValidationError) as caught:
            validate_password("v8#Q2!r")
        self.assertIn("password_too_short", [error.code for error in caught.exception.error_list])


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PasswordWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="024A-032001",
            password="Legacy72!",
            first_name="Clara",
            last_name="Ellison",
            email="student032@example.invalid",
        )
        cls.profile = Profile.objects.create(
            user=cls.user,
            role=Profile.Role.STUDENT,
            student_id=cls.user.username,
            must_change_password=False,
        )
        cls.admin = User.objects.create_superuser(
            username="admin032", email="admin032@example.invalid", password="LegacyAdmin72!"
        )

    def registration_data(self, password):
        return {
            "student_id": "024A-032002",
            "first_name": "Iris",
            "last_name": "Everett",
            "middle_initial": "A",
            "year_level": "2A",
            "email": "iris032@example.invalid",
            "password": password,
            "confirm_password": password,
        }

    def test_registration_enforces_policy_and_keeps_passphrase_whitespace(self):
        invalid = StudentRegistrationForm(self.registration_data(WEAK_PASSWORD))
        self.assertFalse(invalid.is_valid())
        self.assertIn("password", invalid.errors)
        password = "  f8!Vz6@uQ2  "
        form = StudentRegistrationForm(self.registration_data(password))
        self.assertTrue(form.is_valid(), form.errors)
        account = form.save()
        self.assertTrue(account.check_password(password))
        self.assertFalse(account.check_password(password.strip()))
        self.assertNotEqual(account.password, password)

    def test_all_password_forms_reject_a_weak_direct_submission(self):
        for form_class in (
            GuidedSetPasswordForm,
            GuidedPasswordChangeForm,
            TemporaryPasswordForm,
            GuidedAdminPasswordChangeForm,
        ):
            with self.subTest(form=form_class.__name__):
                form = form_class(
                    self.user,
                    {
                        "old_password": "Legacy72!",
                        "new_password1": WEAK_PASSWORD,
                        "new_password2": WEAK_PASSWORD,
                        "password1": WEAK_PASSWORD,
                        "password2": WEAK_PASSWORD,
                        "usable_password": "true",
                    },
                )
                self.assertFalse(form.is_valid())
                errors = [
                    error.code for values in form.errors.as_data().values() for error in values
                ]
                self.assertIn("password_too_guessable", errors)

    def test_password_forms_apply_the_same_eight_to_sixteen_character_limits(self):
        for form_class in (
            GuidedSetPasswordForm,
            GuidedPasswordChangeForm,
            TemporaryPasswordForm,
            GuidedAdminPasswordChangeForm,
        ):
            for password, accepted in (
                ("v8#Q2!r", False),
                ("v8#Q2!rZ", True),
                (STRONG_PASSWORD, True),
                (STRONG_PASSWORD + "!", False),
            ):
                with self.subTest(form=form_class.__name__, length=len(password)):
                    form = form_class(
                        self.user,
                        {
                            "old_password": "Legacy72!",
                            "new_password1": password,
                            "new_password2": password,
                            "password1": password,
                            "password2": password,
                            "usable_password": "true",
                        },
                    )
                    self.assertEqual(form.is_valid(), accepted, form.errors)

    def test_managed_account_creation_checks_every_role(self):
        for role in (Profile.Role.STUDENT, Profile.Role.ORGANIZER, Profile.Role.ADMIN):
            with self.subTest(role=role):
                data = {
                    "role": role,
                    "username": f"032-{role.lower()}",
                    "first_name": "Iris",
                    "last_name": "Everett",
                    "year_level": "2A",
                    "password1": WEAK_PASSWORD,
                    "password2": WEAK_PASSWORD,
                }
                form = ManagedAccountCreateForm(data, roles=tuple(Profile.Role))
                self.assertFalse(form.is_valid())
                data.update(password1=STRONG_PASSWORD, password2=STRONG_PASSWORD)
                form = ManagedAccountCreateForm(data, roles=tuple(Profile.Role))
                self.assertTrue(form.is_valid(), form.errors)
                account = form.save()
                self.assertTrue(account.check_password(STRONG_PASSWORD))

    def test_django_admin_can_still_disable_password_authentication(self):
        form = GuidedAdminPasswordChangeForm(
            self.user,
            {"usable_password": "false", "password1": "a" * 17, "password2": "mismatch"},
        )
        self.assertTrue(form.is_valid(), form.errors)
        account = form.save()
        self.assertFalse(account.has_usable_password())

    def test_existing_short_password_still_logs_in(self):
        response = self.client.post(
            reverse("accounts:student_login"),
            {"username": self.user.username, "password": "Legacy72!"},
        )
        self.assertRedirects(response, reverse("stamps:student_dashboard"))

    def test_existing_password_over_sixteen_characters_can_still_be_changed(self):
        previous = "Legacy password longer than sixteen characters"
        self.user.set_password(previous)
        self.user.save(update_fields=["password"])
        response = self.client.post(
            reverse("accounts:student_login"),
            {"username": self.user.username, "password": previous},
        )
        self.assertRedirects(response, reverse("stamps:student_dashboard"))
        form = GuidedPasswordChangeForm(
            self.user,
            {
                "old_password": previous,
                "new_password1": STRONG_PASSWORD,
                "new_password2": STRONG_PASSWORD,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_current_password_cannot_be_reused(self):
        self.user.set_password(STRONG_PASSWORD)
        self.user.save(update_fields=["password"])
        form = GuidedSetPasswordForm(
            self.user, {"new_password1": STRONG_PASSWORD, "new_password2": STRONG_PASSWORD}
        )
        self.assertFalse(form.is_valid())
        codes = [error.code for values in form.errors.as_data().values() for error in values]
        self.assertIn("password_reused", codes)

    def test_required_password_change_keeps_access_locked_until_valid(self):
        Profile.objects.filter(pk=self.profile.pk).update(must_change_password=True)
        self.client.force_login(self.user)
        url = reverse("accounts:required_password")
        response = self.client.post(
            url, {"new_password1": WEAK_PASSWORD, "new_password2": WEAK_PASSWORD}
        )
        self.assertContains(response, "too easy to guess")
        self.assertNotContains(response, WEAK_PASSWORD)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.must_change_password)
        response = self.client.post(
            url, {"new_password1": STRONG_PASSWORD, "new_password2": STRONG_PASSWORD}
        )
        self.assertRedirects(response, reverse("stamps:student_dashboard"))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.must_change_password)

    def test_reset_link_rejects_weak_password_and_accepts_strong_passphrase(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        response = self.client.get(
            reverse("accounts:password_reset_confirm", args=(uid, token)), follow=True
        )
        self.assertTrue(response.context["validlink"])
        url = response.request["PATH_INFO"]
        response = self.client.post(
            url, {"new_password1": WEAK_PASSWORD, "new_password2": WEAK_PASSWORD}
        )
        self.assertContains(response, "too easy to guess")
        self.assertNotContains(response, WEAK_PASSWORD)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Legacy72!"))
        response = self.client.post(
            url, {"new_password1": STRONG_PASSWORD, "new_password2": STRONG_PASSWORD}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(STRONG_PASSWORD))

    def test_administrator_cannot_set_a_weak_password(self):
        self.client.force_login(self.admin)
        url = reverse("administration:account_password", args=(self.user.pk,))
        response = self.client.post(
            url, {"new_password1": WEAK_PASSWORD, "new_password2": WEAK_PASSWORD}
        )
        self.assertContains(response, "too easy to guess")
        self.assertNotContains(response, WEAK_PASSWORD)
        response = self.client.post(
            url, {"new_password1": STRONG_PASSWORD, "new_password2": STRONG_PASSWORD}
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(STRONG_PASSWORD))

    def test_guidance_appears_on_registration_change_and_django_admin(self):
        response = self.client.get(reverse("accounts:register_student"))
        self.assertContains(response, "data-password-strength")
        self.assertContains(response, "/static/password-strength.js", count=1)
        self.assertContains(response, "at least 8 characters")
        self.assertContains(response, "no more than 16 characters")
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:password_change"))
        self.assertContains(response, "data-password-strength")
        self.assertContains(response, 'id="id_new_password1_helptext"')
        self.client.force_login(self.admin)
        for url in (
            reverse("admin:auth_user_add"),
            reverse("admin:auth_user_password_change", args=(self.user.pk,)),
        ):
            with self.subTest(admin_page=url):
                response = self.client.get(url)
                self.assertContains(response, "data-password-strength")
                self.assertContains(response, "/static/password-strength.js", count=1)
