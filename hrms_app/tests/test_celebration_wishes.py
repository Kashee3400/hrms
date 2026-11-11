from datetime import date
from unittest import mock

from hrms_app.models import CelebrationWish, Notification, PersonalDetails
from hrms_app.services.mobile import celebration_wishes as wishes
from hrms_app.services.mobile.celebrations import get_celebrations
from hrms_app.tests.base import MobileTestCase

TODAY = date(2026, 11, 15)


class WishTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(wishes.transaction, "on_commit", lambda fn: fn())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.mail = mock.patch.object(wishes, "send_leave_application_email").start()
        self.addCleanup(mock.patch.stopall)

        self.vikrant = self.person(9, official_email="vikrant@k.co")
        PersonalDetails.objects.filter(user=self.vikrant).update(birthday=date(1992, 11, 15))
        self.vikrant.refresh_from_db()
        self.me = self.person(65)

    def wish(self, kind="birthday", message="Happy Birthday! Have a great year.", sender=None, to=None):
        return wishes.send_wish(sender or self.me, (to or self.vikrant).pk, kind, message, today=TODAY)

    def test_wish_reaches_them_three_ways(self):
        self.assertIsNone(self.wish())
        note = Notification.objects.get(receiver=self.vikrant)
        self.assertEqual(note.message, "P65 Name wished you a Happy Birthday: Happy Birthday! Have a great year.")
        subject, body, to = self.mail.delay.call_args.args
        self.assertEqual((subject, to), ("Happy Birthday from P65 Name", ["vikrant@k.co"]))
        self.assertIn("Happy Birthday! Have a great year.", body)

    def test_once_per_occasion(self):
        self.wish()
        self.assertEqual(self.wish(message="Again"), "You have already wished them today.")
        self.assertEqual(CelebrationWish.objects.count(), 1)

    def test_only_on_the_day(self):
        problem = wishes.send_wish(self.me, self.vikrant.pk, "birthday", "Hi", today=date(2026, 11, 14))
        self.assertEqual(problem, "There's nothing to celebrate for this employee today.")
        self.assertIsNotNone(self.wish(kind="marriage"))

    def test_not_yourself_and_message_needed(self):
        self.assertEqual(self.wish(message="  "), "Please write a message.")
        self.assertEqual(self.wish(message="x" * 301), "Keep the message under 300 characters.")
        self.assertEqual(self.wish(sender=self.vikrant), "You can't wish yourself.")

    def test_celebrations_show_count_and_whether_i_wished(self):
        self.wish()
        other = self.person(10)
        wishes.send_wish(other, self.vikrant.pk, "birthday", "HBD", today=TODAY)
        item = next(i for i in get_celebrations(TODAY, str, viewer=self.me) if i["user_id"] == self.vikrant.pk)
        self.assertEqual((item["is_today"], item["wish_count"], item["wished_by_me"], item["is_me"]), (True, 2, True, False))
        own = next(i for i in get_celebrations(TODAY, str, viewer=self.vikrant) if i["user_id"] == self.vikrant.pk)
        self.assertEqual((own["is_me"], own["wished_by_me"]), (True, False))

    def test_only_the_celebrant_reads_messages(self):
        self.wish()
        rows = wishes.wishes_received(self.vikrant, "birthday", today=TODAY)
        self.assertEqual([(r["name"], r["message"]) for r in rows], [("P65 Name", "Happy Birthday! Have a great year.")])
        self.assertEqual(wishes.wishes_received(self.me, "birthday", today=TODAY), [])


class WishApiTests(MobileTestCase):
    def test_bad_input_and_login(self):
        me = self.person(65)
        client = self.client_for(me)
        self.assertEqual(client.post("/api/v1/celebrations/wish/", {"user_id": "x", "kind": "birthday"}, format="json").status_code, 400)
        self.assertEqual(client.get("/api/v1/celebrations/wishes/", {"kind": "nope"}).status_code, 400)
        self.assertEqual(client.get("/api/v1/celebrations/wishes/", {"kind": "birthday"}).data["data"], {"wishes": []})
        self.client.logout()
        self.assertEqual(self.client.post("/api/v1/celebrations/wish/").status_code, 401)
