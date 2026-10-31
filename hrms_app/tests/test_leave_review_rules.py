from types import SimpleNamespace as NS

from django.test import SimpleTestCase

from hrms_app.services.mobile.team_leaves import _review_actions

ADMIN = NS(designation=NS(department=NS(department="admin")))
OPS = NS(designation=NS(department=NS(department="operations")))
MANAGER = NS(pk=1, is_superuser=False, personal_detail=OPS)
CEO = NS(pk=2, is_superuser=False, personal_detail=ADMIN)
OTHER = NS(pk=3, is_superuser=False, personal_detail=OPS)


def leave(status, code="CL", reports_to=1, applicant=9):
    return NS(
        status=status,
        appliedBy_id=applicant,
        appliedBy=NS(reports_to_id=reports_to),
        leave_type=NS(leave_type_short_code=code),
    )


class ReviewRuleTests(SimpleTestCase):
    CASES = [
        ("CL pending, manager", MANAGER, leave("pending"), ["Approve", "Reject"]),
        ("CL approved, manager", MANAGER, leave("approved"), []),
        ("CL rejected, manager", MANAGER, leave("rejected"), []),
        ("CL cancelled, manager", MANAGER, leave("cancelled"), []),
        ("CL cancel request, manager", MANAGER, leave("pending_cancellation"), ["Cancel Leave"]),
        ("CL pending, admin not manager", CEO, leave("pending"), []),
        ("CL pending, unrelated", OTHER, leave("pending"), []),
        ("LWP pending, manager", MANAGER, leave("pending", "LWP"), ["Recommend", "Reject"]),
        ("LWP pending, admin not manager", CEO, leave("pending", "LWP"), []),
        ("LWP pending, admin is manager", CEO, leave("pending", "LWP", 2), ["Approve", "Reject"]),
        ("LWP recommended, manager", MANAGER, leave("recommended", "LWP"), []),
        ("LWP recommended, admin", CEO, leave("recommended", "LWP"), ["Approve", "Reject"]),
        ("LWP not recommended, manager", MANAGER, leave("not recommended", "LWP"), []),
        ("LWP not recommended, admin", CEO, leave("not recommended", "LWP"), []),
        ("LWP cancel request, manager", MANAGER, leave("pending_cancellation", "LWP"), ["Cancel Leave"]),
        ("LWP cancel request, admin", CEO, leave("pending_cancellation", "LWP"), []),
        ("own leave", MANAGER, leave("pending", applicant=1), []),
    ]

    def test_who_can_do_what(self):
        for name, user, item, expected in self.CASES:
            with self.subTest(name):
                self.assertEqual([label for _, label in _review_actions(user, item)], expected)
