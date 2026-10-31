from datetime import date, datetime, timedelta
from unittest import mock

from django.conf import settings
from django.utils import timezone

from hrms_app.models import AttendanceLog, AttendanceStatusColor, DeviceInformation
from hrms_app.services.mobile import team_attendance as team
from hrms_app.services.mobile.team_out import team_out
from hrms_app.tests.base import MobileTestCase, at

MONDAY = date(2030, 1, 7)


class TeamTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        DeviceInformation.objects.create(
            device_location=self.location, serial_number="1", username="u", password="p", from_date=now, to_date=now
        )
        AttendanceStatusColor.objects.create(status="Present", color_hex="#06B900")
        self.boss = self.person(1)
        self.a = self.person(2, reports_to=self.boss)
        self.b = self.person(3, reports_to=self.boss)
        self.c = self.person(4, reports_to=self.boss)
        self.d = self.person(5, reports_to=self.boss)
        self.person(6, reports_to=self.boss, is_active=False)
        self.outsider = self.person(7)
        self.today = timezone.localdate()
        self.client_boss = self.client_for(self.boss)

        plan = {self.b.pk: "CL", self.c.pk: "T"}

        def fake_codes(user, start, end, today):
            days = {start + timedelta(n): ("A", "#FF0000") for n in range((end - start).days + 1)}
            days[today] = (plan.get(user.pk), "#000EB0" if user.pk in plan else None)
            return days

        patcher = mock.patch.object(team, "day_codes", fake_codes)
        patcher.start()
        self.addCleanup(patcher.stop)

    def soap(self, **kwargs):
        return mock.patch.object(team, "call_soap_api", **kwargs)

    def test_today_headcount(self):
        with self.soap(return_value={"2": {self.today: [datetime.now()]}}) as call:
            data = self.client_boss.get("/api/v1/attendance/team/today/").data["data"]
        self.assertEqual(
            (data["total"], data["present"], data["leave"], data["tour"], data["not_in"]), (4, 1, 1, 1, 1)
        )
        self.assertTrue(data["device_available"])
        self.assertEqual(call.call_count, 1)  # one call per device, inactive left out

    def test_no_reportees(self):
        data = self.client_for(self.outsider).get("/api/v1/attendance/team/today/").data["data"]
        self.assertEqual(data, {"has_team": False})

    def test_device_down_is_reported_not_zeroed(self):
        for kwargs in ({"return_value": None}, {"side_effect": OSError("down")}):
            with self.soap(**kwargs), self.assertLogs(team.logger, "ERROR") if "side_effect" in kwargs else self.subTest():
                data = self.client_boss.get("/api/v1/attendance/team/today/").data["data"]
            self.assertFalse(data["device_available"])

    def month(self):
        return self.client_boss.get(
            "/api/v1/attendance/team/", {"year": self.today.year, "month": self.today.month}
        ).data["data"]

    def test_month_grid(self):
        with self.soap(return_value={"2": {self.today: [datetime.now()]}}):
            data = self.month()
        self.assertEqual([m["is_self"] for m in data["members"]], [True, False, False, False, False])
        cells = {m["code"]: {d["date"]: d for d in m["days"]} for m in data["members"]}
        punched = cells["KMPCL-002"][str(self.today)]
        self.assertEqual((punched["code"], punched["category"]), ("P", "present"))
        self.assertIsNone(cells["KMPCL-005"][str(self.today)]["code"])

    def test_missing_punch_is_per_person(self):
        day = self.today.replace(day=1) if self.today.day != 1 else self.today
        AttendanceLog.objects.create(
            applied_by=self.a, start_date=at(day), end_date=at(day), reg_status=settings.MIS_PUNCHING, slug="m1", title="m1"
        )
        with self.soap(return_value={}):
            data = self.month()
        flags = {m["code"]: m["days"][0]["missing_punch"] for m in data["members"]}
        self.assertTrue(flags["KMPCL-002"])
        self.assertFalse(flags["KMPCL-003"])

    def test_day_detail_is_limited_to_reportees(self):
        url = f"/api/v1/attendance/team/{self.b.pk}/day/"
        day = str(self.today)
        with mock.patch.object(team, "get_month_calendar", return_value={"days": [{"date": day, "code": "CL"}]}):
            self.assertEqual(self.client_boss.get(url, {"date": day}).data["data"]["day"]["code"], "CL")
            self.assertEqual(self.client_for(self.outsider).get(url, {"date": day}).status_code, 404)
            self.assertEqual(self.client_boss.get(url, {"date": "x"}).status_code, 400)
            own = f"/api/v1/attendance/team/{self.boss.pk}/day/"
            self.assertEqual(self.client_boss.get(own, {"date": day}).status_code, 200)

    def test_bad_month_and_no_login(self):
        self.assertEqual(self.client_boss.get("/api/v1/attendance/team/", {"month": 13}).status_code, 400)
        self.client.logout()
        self.assertEqual(self.client.get("/api/v1/attendance/team/").status_code, 401)


class TeamOutTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        self.boss = self.person(1)
        self.a = self.person(2, reports_to=self.boss)
        self.b = self.person(3, reports_to=self.boss)
        self.c = self.person(4, reports_to=self.boss)
        self.mine = self.leave(self.a, MONDAY, settings.PENDING, days=2)
        self.leave(self.b, MONDAY + timedelta(1), settings.APPROVED)
        self.leave(self.b, MONDAY + timedelta(5), settings.APPROVED)  # after the request
        self.leave(self.c, MONDAY, settings.REJECTED)
        self.tour(self.c, MONDAY - timedelta(3), MONDAY - timedelta(1), settings.EXTENDED, extended=MONDAY)

    def test_only_overlapping_live_requests(self):
        out = team_out(self.boss, self.a, MONDAY, MONDAY + timedelta(1))
        self.assertEqual(out["team_size"], 2)
        self.assertEqual(
            [(p["code"], p["label"]) for p in out["people"]], [("KMPCL-004", "Tour"), ("KMPCL-003", "CL")]
        )

    def test_someone_elses_reportee_shows_nothing(self):
        admin = self.person(9, designation=self.admin_designation)
        self.assertIsNone(team_out(admin, self.a, MONDAY, MONDAY))

    def test_shown_on_open_requests_only(self):
        client = self.client_for(self.boss)
        data = client.get(f"/api/v1/leave/team/{self.mine.pk}/").data["data"]
        self.assertEqual(len(data["team_out"]["people"]), 2)
        decided = self.leave(self.a, MONDAY + timedelta(14), settings.APPROVED)
        self.assertIsNone(client.get(f"/api/v1/leave/team/{decided.pk}/").data["data"]["team_out"])
        tour = self.tour(self.a, MONDAY, MONDAY, settings.PENDING)
        self.assertEqual(client.get(f"/api/v1/tour/team/{tour.pk}/").data["data"]["team_out"]["team_size"], 2)
