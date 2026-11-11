"""Birthdays and anniversaries of the next week, for the Home screen. Same three
occasions as the greeting emails. Only the day is shared, never a birth year."""
from collections import Counter
from datetime import date, timedelta

from hrms_app.models import CelebrationWish, PersonalDetails
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


def _occasions(details):
    return ((BIRTHDAY, details.birthday), (MARRIAGE, details.marriage_ann), (WORK, details.doj))


def occasions_on(user, today):
    """The kinds ``user`` celebrates on ``today`` (the joining day itself isn't one)."""
    details = getattr(user, "personal_detail", None)
    if details is None:
        return set()
    return {
        kind
        for kind, original in _occasions(details)
        if original and _next_date(original, today) == today and not (kind == WORK and today.year == original.year)
    }


def get_celebrations(today, build_url, viewer=None):
    rows = PersonalDetails.objects.filter(user__is_active=True).select_related("user", "designation")
    last = today + timedelta(days=WINDOW_DAYS)
    wishes = CelebrationWish.objects.filter(occasion_date=today)
    counts = Counter(wishes.values_list("receiver_id", "kind"))
    mine = set(wishes.filter(sender=viewer).values_list("receiver_id", "kind")) if viewer else set()
    items = []
    for details in rows:
        user = details.user
        name = user.get_full_name() or user.username
        avatar = build_url(details.avatar.url) if details.avatar else None
        for kind, original in _occasions(details):
            if not original:
                continue
            day = _next_date(original, today)
            if day is None or day > last:
                continue
            years = day.year - original.year if kind == WORK else None
            if kind == WORK and years < 1:
                continue  # the joining day itself
            is_today = day == today
            items.append(
                {
                    "user_id": user.pk,
                    "name": name,
                    "designation": str(details.designation) if details.designation else None,
                    "avatar_url": avatar,
                    "kind": kind,
                    "date": iso_date(day),
                    "is_today": is_today,
                    "years": years,
                    "wish_count": counts[(user.pk, kind)] if is_today else 0,
                    "wished_by_me": (user.pk, kind) in mine,
                    "is_me": viewer is not None and user.pk == viewer.pk,
                }
            )
    return sorted(items, key=lambda item: (item["date"], item["name"]))
