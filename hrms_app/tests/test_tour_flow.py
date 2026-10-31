from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Permission
from django.utils import timezone

from hrms_app.models import CustomUser, LockStatus, UserTour
from hrms_app.services.mobile import team_tours, tours
from hrms_app.tests.base import MobileTestCase


class TourFlowTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("hrms_app.services.mobile.tours.send_tour_notifications")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.manager = self.person(1)
        emp = self.person(7, reports_to=self.manager)
        emp.user_permissions.add(
            *Permission.objects.filter(codename__in=["add_usertour", "change_usertour", "delete_usertour"])
        )
        self.emp = CustomUser.objects.get(pk=emp.pk)
        self.future = timezone.localdate() + timedelta(days=30)
        self.mine = self.client_for(self.emp)
        self.boss = self.client_for(self.manager)

    def body(self, **extra):
        return {
            "approval_type": "pre approval",
            "from_destination": "Varanasi",
            "to_destination": "Lucknow",
            "start_date": self.future.isoformat(),
            "start_time": "09:00",
            "end_date": (self.future + timedelta(days=1)).isoformat(),
            "end_time": "18:00",
            "remarks": "Audit",
            **extra,
        }

    def apply(self):
        res = self.mine.post("/api/v1/tour/my/", self.body(), format="json")
        self.assertEqual(res.status_code, 201 if res.status_code == 201 else 200, res.data)
        return res.data["data"]["id"]

    def act(self, tour_id, status, remark=""):
        return self.boss.post(
            f"/api/v1/tour/team/{tour_id}/action/", {"status": status, "remark": remark}, format="json"
        )

    def test_bad_forms_are_refused(self):
        self.assertTrue(tours.save_tour(self.emp, {})[1])
        self.assertTrue(tours.save_tour(self.emp, self.body(start_date="xx"))[1])
        before = (self.future - timedelta(days=2)).isoformat()
        self.assertTrue(tours.save_tour(self.emp, self.body(end_date=before))[1])
        self.assertTrue(tours.save_tour(self.emp, self.body(approval_type="post approval"))[1])

    def test_apply_approve_cancel(self):
        tour_id = self.apply()
        detail = self.boss.get(f"/api/v1/tour/team/{tour_id}/").data["data"]
        self.assertEqual([a["label"] for a in detail["allowed_actions"]], ["Approve", "Reject"])

        self.assertEqual(self.act(tour_id, "rejected").data["message"], "Reason is required when rejecting a tour.")
        self.assertEqual(self.act(tour_id, "cancelled").data["message"], "This action is not allowed for this tour.")
        self.assertEqual(self.act(tour_id, "approved", "Go").status_code, 200)
        self.assertEqual(UserTour.objects.get(pk=tour_id).status, "approved")

        cancel = f"/api/v1/tour/my/{tour_id}/cancel/"
        self.assertNotEqual(self.mine.post(cancel, {"reason": ""}, format="json").status_code, 200)
        self.assertEqual(self.mine.post(cancel, {"reason": "Plan changed"}, format="json").status_code, 200)
        detail = self.boss.get(f"/api/v1/tour/team/{tour_id}/").data["data"]
        self.assertEqual([a["label"] for a in detail["allowed_actions"]], ["Cancel Tour"])
        self.assertEqual(self.act(tour_id, "cancelled").status_code, 200)
        self.assertEqual(self.boss.get(f"/api/v1/tour/team/{tour_id}/").data["data"]["allowed_actions"], [])

    def test_lock_stops_editing_and_review(self):
        day = self.future + timedelta(days=5)
        tour, _ = tours.save_tour(self.emp, self.body(start_date=day.isoformat(), end_date=day.isoformat()))
        LockStatus.objects.create(is_locked="locked", from_date=day, to_date=day + timedelta(days=1), reason="Audit")
        item = tours.tour_item(self.emp, UserTour.objects.get(pk=tour.pk))
        self.assertEqual((item["is_locked"], item["can_edit"], item["can_delete"]), (True, False, False))
        self.assertIsNotNone(team_tours.act(self.manager, UserTour.objects.get(pk=tour.pk), "approved"))

    def test_strangers_see_nothing(self):
        tour_id = self.apply()
        stranger = self.client_for(self.person(9))
        self.assertEqual(stranger.get(f"/api/v1/tour/my/{tour_id}/").status_code, 404)
