"""The year's holidays that apply to this employee (blank applicable users = everyone)."""
from datetime import date

from hrms_app.services.mobile.attendance_codes import applicable_holidays
from hrms_app.services.mobile.formatters import iso_date, plain_text


def get_holidays(user, year):
    holidays = applicable_holidays(user, date(year, 1, 1), date(year, 12, 31))
    return {
        "year": year,
        "holidays": [
            {
                "id": holiday.pk,
                "title": holiday.title,
                "short_code": holiday.short_code,
                "start_date": iso_date(holiday.start_date),
                "end_date": iso_date(holiday.end_date),
                "color": holiday.color_hex,
                "description": plain_text(holiday.desc),
            }
            for holiday in holidays.order_by("start_date", "pk")
        ],
    }
