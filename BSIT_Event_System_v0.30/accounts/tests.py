from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile


class DashboardNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.accounts = {}
        for role in (Profile.Role.STUDENT, Profile.Role.ORGANIZER, Profile.Role.ADMIN):
            user = User.objects.create_user(username=f"navigation-{role.lower()}")
            Profile.objects.create(user=user, role=role, must_change_password=False)
            # Organizer creation requires a password change. These fixtures model accounts
            # that have already completed that first sign-in step.
            Profile.objects.filter(user=user).update(must_change_password=False)
            cls.accounts[role] = user

    def test_dashboards_and_account_pages_keep_the_shared_sidebar(self):
        routes = {
            Profile.Role.STUDENT: (
                "stamps:student_dashboard",
                "stamps:student_qr_page",
                "stamps:student_stamps_page",
                "stamps:student_history_page",
                "accounts:profile",
                "accounts:password_change",
                "accounts:notifications",
            ),
            Profile.Role.ORGANIZER: (
                "events:organizer_dashboard",
                "events:organizer_events",
                "events:event_create",
                "accounts:profile",
                "accounts:password_change",
                "accounts:notifications",
            ),
            Profile.Role.ADMIN: (
                "administration:dashboard",
                "administration:accounts",
                "administration:events",
                "administration:attendance",
                "administration:activity",
            ),
        }
        for role, names in routes.items():
            self.client.force_login(self.accounts[role])
            for name in names:
                with self.subTest(role=role, page=name):
                    response = self.client.get(reverse(name))
                    self.assertContains(response, 'id="dashboard-sidebar"', count=1)
                    self.assertContains(response, 'aria-controls="dashboard-sidebar"', count=2)
                    self.assertContains(response, 'data-sidebar-toggle', count=1)
                    self.assertContains(response, 'data-sidebar-open', count=1)
                    self.assertContains(response, 'id="dashboard-bottom-navigation"', count=1)
                    self.assertContains(response, "/static/sidebar.js", count=1)
                    self.assertContains(response, f"bsit.sidebar.{role.lower()}.")
                    self.assertNotContains(response, 'class="navbar student-navbar')

    def test_public_landing_keeps_role_sign_in_panels(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'id="student-panel"')
        self.assertContains(response, 'id="organizer-panel"')
        self.assertNotContains(response, 'id="dashboard-sidebar"')
        self.assertNotContains(response, 'id="dashboard-bottom-navigation"')
