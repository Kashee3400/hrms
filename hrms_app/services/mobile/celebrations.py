"""Birthdays and anniversaries of the next week, for the Home screen. Same three
occasions as the greeting emails. Only the day is shared, never a birth year."""
from datetime import date, timedelta

from hrms_app.models import PersonalDetails
from hrms_app.services.mobile.formatters import iso_date

WINDOW_DAYS = 7
BIRTHDAY, MARRIAGE, WORK = "birthday", "marriage", "work"


def _next_date(original, today):
    """This occasion's next date from today, or None. 29 Feb falls on 28 Feb."""
    for year in (today.year, today.year + 1):
        try:
            candidate = original.replace(year=year)
        except ValueError:
            candidate = date(year, 2, 28)
        if candidate >= today:
            return candidate
    return None


def get_celebrations(today, build_url):
    rows = PersonalDetails.objects.filter(user__is_active=True).select_related("user")
    last = today + timedelta(days=WINDOW_DAYS)
    items = []
    for details in rows:
        name = details.user.get_full_name() or details.user.username
        avatar = build_url(details.avatar.url) if details.avatar else None
        for kind, original in ((BIRTHDAY, details.birthday), (MARRIAGE, details.marriage_ann), (WORK, details.doj)):
            if not original:
                continue
            day = _next_date(original, today)
            if day is None or day > last:
                continue
            years = day.year - original.year if kind == WORK else None
            if kind == WORK and years < 1:
                continue  # the joining day itself
            items.append(
                {
                    "name": name,
                    "avatar_url": avatar,
                    "kind": kind,
                    "date": iso_date(day),
                    "is_today": day == today,
                    "years": years,
                }
            )
    return sorted(items, key=lambda item: (item["date"], item["name"]))
