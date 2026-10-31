from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from hrms_app import tasks
from hrms_app.models import AllowedUserExpiry, AppSetting, CustomUser
from hrms_app.tests.base import MobileTestCase


class TourApiAccessTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        self.emp = self.person(7)
        today = timezone.localdate()
        self.item = self.tour(self.emp, today, today, "approved")

    def test_needs_staff(self):
        url = f"/api/v1/tours/{self.item.pk}/"
        self.assertEqual(APIClient().get("/api/v1/tours/").status_code, 401)
        self.assertEqual(APIClient().put(url, {"status": "approved"}, format="json").status_code, 401)
        self.assertEqual(self.client_for(self.emp).get(url).status_code, 403)
        root = CustomUser.objects.create_user(username="root", password="x", is_superuser=True, is_staff=True)
        self.assertEqual(self.client_for(root).get(url).status_code, 200)


class PasswordChangeTests(MobileTestCase):
    def phone(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    def test_signs_out_other_phones(self):
        emp = self.person(7, password="OldPass#123")
        login = APIClient().post(
            "/api/v1/token/", {"username": "KMPCL-007", "password": "OldPass#123"}, format="json"
        )
        phone = self.phone(login.data["access"])
        legacy = self.phone(str(RefreshToken.for_user(emp).access_token))
        self.assertEqual(phone.get("/api/v1/app-settings/").status_code, 403)  # signed in, not superuser

        changed = phone.post(
            "/api/v1/profile/change-password/",
            {"old_password": "OldPass#123", "new_password1": "Zebra#Mango91", "new_password2": "Zebra#Mango91"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(phone.get("/api/v1/app-settings/").status_code, 401)

        refreshed = APIClient().post("/api/v1/token/refresh/", {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(self.phone(refreshed.data.get("access", "x")).get("/api/v1/app-settings/").status_code, 401)
        # Tokens issued before the stamp existed stay valid.
        self.assertEqual(legacy.get("/api/v1/app-settings/").status_code, 403)


class AllowedUserExpiryTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        self.root = CustomUser.objects.create_user(username="root", password="x", is_superuser=True, is_staff=True)
        self.emp = self.person(7)
        self.other = self.person(8)
        self.today = timezone.localdate()
        self.setting = AppSetting.objects.create(key="TOUR_LIMIT", value="4", beyond_policy=False)

    def put(self, **body):
        return self.client_for(self.root).put(
            "/api/v1/app-settings/TOUR_LIMIT/", {"value": "4", "beyond_policy": False, **body}, format="json"
        )

    def test_new_employee_needs_a_future_end_date(self):
        self.assertEqual(
            self.put(allowed_users=[self.emp.pk]).data["message"], "Select the Allowed Until date."
        )
        past = str(self.today - timedelta(days=1))
        self.assertEqual(
            self.put(allowed_users=[self.emp.pk], allowed_until=past).data["message"],
            "Allowed Until can't be in the past.",
        )

    def test_removed_after_the_end_date(self):
        self.put(allowed_users=[self.emp.pk], allowed_until=str(self.today))
        self.setting.allowed_users.add(self.other)  # as if added on the web, no end date
        self.assertEqual(tasks.remove_expired_allowed_users(), 0)
        AllowedUserExpiry.objects.filter(user=self.emp).update(expires_on=self.today - timedelta(days=1))
        self.assertEqual(tasks.remove_expired_allowed_users(), 1)
        self.assertEqual(list(self.setting.allowed_users.values_list("pk", flat=True)), [self.other.pk])
        self.assertEqual(tasks.remove_expired_allowed_users(), 0)
