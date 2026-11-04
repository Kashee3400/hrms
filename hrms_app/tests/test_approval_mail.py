from types import SimpleNamespace as NS

from hrms_app.services import approval_mail
from hrms_app.tests.base import MobileTestCase

REASON = "My grandmother passed away on 22 September 2026, so I had to travel home urgently."


class ApprovalMailTextTests(MobileTestCase):
    def setUp(self):
        super().setUp()
        self.boss = self.person(4, official_email="boss@k.co")
        self.emp = self.person(65, official_email="emp@k.co", reports_to=self.boss)

    def compose(self, note="EL should be applied at least 7.0 days in advance."):
        request = {
            "title": "Earned Leave (EL) from 22 Sep 2026 to 26 Sep 2026",
            "action": "apply for Earned Leave (EL) from 22 Sep 2026 to 26 Sep 2026",
            "note": note,
        }
        return approval_mail._compose(self.emp, request, REASON)

    def test_reads_like_the_employees_letter(self):
        body = self.compose()["body"]
        print("\n" + body)
        self.assertTrue(body.startswith(f"Dear Sir,\n\n{REASON}\n\nI request your approval to apply for Earned Leave (EL)"))
        self.assertIn("at least 7 days in advance.", body)
        self.assertIn("sent from HRMS on behalf of P65 Name (KMPCL-065)", body)
        self.assertNotIn("\n\n\n", body)

    def test_reason_is_not_html_escaped(self):
        mail = approval_mail._compose(
            self.emp, {"title": "T", "action": "a", "note": ""}, "Tom & Jerry's \"show\" <b>"
        )
        self.assertIn("Tom & Jerry's \"show\" <b>", mail["body"])
        self.assertNotIn("HRMS did not allow", mail["body"])

    def test_subject_and_recipients(self):
        mail = self.compose()
        self.assertEqual(
            mail["subject"],
            "Approval request: Earned Leave (EL) from 22 Sep 2026 to 26 Sep 2026 - P65 Name (KMPCL-065)",
        )
        self.assertEqual(mail["to"], "boss@k.co")
        self.assertIn("emp@k.co", mail["cc"])
