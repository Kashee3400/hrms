from django.test import SimpleTestCase

from hrms_app.models import TourStatusLog
from hrms_app.services.mobile.formatters import timeline
from hrms_app.services.mobile.tours import tour_detail
from hrms_app.tests.base import MobileTestCase


def entry(action, at, by="Manager", notes=""):
    return {"action": action, "by": by, "at": f"2026-09-21T13:{at}+05:30", "notes": notes}


class TimelineTests(SimpleTestCase):
    def test_newest_first(self):
        rows = timeline([entry("Created", "35:00", by="Emp"), entry("approved", "36:00")])
        self.assertEqual([row["action"] for row in rows], ["approved", "Created"])

    def test_web_double_log_shows_once(self):
        rows = timeline([entry("approved", "36:00", notes="Go"), entry("Approve", "36:01")])
        self.assertEqual([(row["action"], row["notes"]) for row in rows], [("approved", "Go")])

    def test_note_on_the_second_row_is_kept(self):
        rows = timeline([entry("Extended", "36:00"), entry("extended", "36:05", notes="Two more days")])
        self.assertEqual([(row["action"], row["notes"]) for row in rows], [("extended", "Two more days")])

    def test_exact_repeats_merge(self):
        self.assertEqual(len(timeline([entry("approved", "36:00"), entry("approved", "36:00")])), 1)

    def test_a_real_second_decision_stays(self):
        self.assertEqual(len(timeline([entry("approved", "36:00"), entry("approved", "40:00")])), 2)

    def test_different_people_stay(self):
        rows = [entry("recommended", "36:00", by="Manager"), entry("recommended", "36:10", by="Admin")]
        self.assertEqual(len(timeline(rows)), 2)

    def test_different_actions_stay(self):
        self.assertEqual(len(timeline([entry("Created", "36:00"), entry("Updated", "36:10")])), 2)

    def test_empty(self):
        self.assertEqual(timeline([]), [])


class TourDetailTimelineTests(MobileTestCase):
    def test_the_screenshot_case(self):
        boss = self.person(1)
        emp = self.person(7, reports_to=boss)
        item = self.tour(emp, "2026-09-19", "2026-09-20", "approved")
        TourStatusLog.create_log(tour=item, action_by=emp, action="Created")
        TourStatusLog.create_log(tour=item, action_by=boss, action="approved")
        TourStatusLog.create_log(tour=item, action_by=boss, action="Approve")
        logs = tour_detail(emp, item, lambda path: path)["logs"]
        self.assertEqual([log["action"] for log in logs], ["approved", "Created"])
        self.assertEqual(TourStatusLog.objects.filter(tour=item).count(), 3)  # stored rows untouched
