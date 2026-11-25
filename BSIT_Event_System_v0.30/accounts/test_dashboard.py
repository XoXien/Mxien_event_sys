"""Regressions for dashboard upgrades, administrator routes, and dependency setup."""

import os
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import Resolver404, resolve, reverse
from django.utils.crypto import salted_hmac

from .checks import check_password_estimator
from .models import Profile
from .password_forms import GuidedSetPasswordForm
from .password_policy import GuessablePasswordValidator
from .templatetags.static_assets import asset


class PageAssets(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.urls = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.urls.append(attrs["href"])
        elif tag == "script" and attrs.get("src"):
            self.urls.append(attrs["src"])


class AssetVersionTests(SimpleTestCase):
    def test_changed_file_gets_a_new_url_without_a_manual_release_number(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "dashboard-test.css"
            path.write_text("nav { width: 76px; }")
            with override_settings(STATICFILES_DIRS=[directory]):
                first = asset("dashboard-test.css")
                self.assertEqual(first, asset("dashboard-test.css"))
                modified = path.stat().st_mtime_ns
                path.write_text("nav { width: 99px; }")
                os.utime(path, ns=(modified + 1_000_000, modified + 1_000_000))
                second = asset("dashboard-test.css")
                self.assertNotEqual(first, second)
                self.assertRegex(second, r"/dashboard-test\.css\?v=[0-9a-f]{16}$")


class PasswordDependencyTests(SimpleTestCase):
    def test_missing_estimator_has_an_actionable_system_check(self):
        with patch(
            "accounts.checks.import_module",
            side_effect=ModuleNotFoundError(name="zxcvbn"),
        ):
            errors = check_password_estimator(None)
        self.assertEqual([error.id for error in errors], ["accounts.W001"])
        self.assertIn("python -m pip install -r requirements.txt", errors[0].hint)

    def test_missing_estimator_does_not_accept_an_unchecked_password(self):
        with (
            patch(
                "accounts.password_policy.import_module",
                side_effect=ModuleNotFoundError(name="zxcvbn"),
            ),
            self.assertRaises(ValidationError) as caught,
        ):
            GuessablePasswordValidator().validate("v8#Q2!rZ")
        self.assertEqual(caught.exception.code, "password_checker_unavailable")


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class DashboardUpgradeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user("024A-035001", password="Existing35!")
        Profile.objects.create(user=cls.student, role=Profile.Role.STUDENT)
        cls.organizer = User.objects.create_user("organizer035", password="Existing35!")
        Profile.objects.create(user=cls.organizer, role=Profile.Role.ORGANIZER)
        Profile.objects.filter(user=cls.organizer).update(must_change_password=False)
        cls.admin = User.objects.create_superuser("admin035", password="Existing35!")

    def test_fixed_administrator_address_keeps_authentication_and_role_checks(self):
        self.assertEqual(reverse("administration:dashboard"), "/bsiteventsysadmin/")
        self.assertEqual(reverse("admin:index"), "/bsiteventsysadmin/django/")
        response = self.client.get("/bsiteventsysadmin/")
        self.assertRedirects(
            response,
            "/bsiteventsysadmin/login/?next=/bsiteventsysadmin/",
        )
        for user in (self.student, self.organizer):
            self.client.force_login(user)
            self.assertEqual(self.client.get("/bsiteventsysadmin/").status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/bsiteventsysadmin/").status_code, 200)

    def test_old_admin_addresses_are_no_longer_registered(self):
        old_path = salted_hmac(
            "bsit-events.admin-portal-path", "portal", algorithm="sha256"
        ).hexdigest()[:32]
        for path in ("/admin/", f"/{old_path}/"):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path)

    def test_all_roles_and_their_account_pages_load_matching_current_assets(self):
        for user, dashboard in (
            (self.student, "stamps:student_dashboard"),
            (self.organizer, "events:organizer_dashboard"),
            (self.admin, "administration:dashboard"),
        ):
            self.client.force_login(user)
            account_page = (
                "administration:accounts" if user.is_superuser else "accounts:profile"
            )
            for route in (dashboard, account_page):
                with self.subTest(user=user.username, route=route):
                    response = self.client.get(reverse(route))
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, "data-dashboard-layout")
                    urls = PageAssets(response.content.decode()).urls
                    self.assertTrue(urls)
                    for url in urls:
                        if url.startswith("/static/"):
                            self.assertRegex(url, r"\?v=[0-9a-f]{16}$")
                            name = url.split("/static/", 1)[1].split("?", 1)[0]
                            self.assertEqual(url, asset(name))
                    self.assertIn(asset("css/sidebar.css"), urls)
                    self.assertIn(asset("sidebar.js"), urls)

    def test_missing_estimator_keeps_the_existing_password_unchanged(self):
        form = GuidedSetPasswordForm(
            self.student,
            {"new_password1": "v8#Q2!rZ", "new_password2": "v8#Q2!rZ"},
        )
        with patch(
            "accounts.password_policy.import_module",
            side_effect=ModuleNotFoundError(name="zxcvbn"),
        ):
            self.assertFalse(form.is_valid())
        self.assertIn(
            "password_checker_unavailable",
            [
                error.code
                for errors in form.errors.as_data().values()
                for error in errors
            ],
        )
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password("Existing35!"))
