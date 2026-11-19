from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
import re

from .inputs import Fields, finite, integer, number, string

DATE = re.compile(r"([+-]?\d{1,6})-([+-]?\d{1,6})-([+-]?\d{1,6})")
LEAVE = re.compile(
    r"(?<![\w./–—-])(?:(?:(?P<start>\d+(?:\.\d+)?)(?P<join>\s*[-–—]\s*|\s+(?:to|or)\s+))?"
    r"(?P<amount>\d+(?:\.\d+)?)[ -]+days?|(?:a\s+)?(?P<half>half[- ]day))\b"
    r"(?:\s*(?:/|per\s+)\s*(?:calendar\s+)?(?P<period>month|year)\b)?", re.IGNORECASE
)
DAYS = re.compile(r"\b(?:half[- ]day|days?)\b", re.IGNORECASE)


def clamp_date(year: int, month: int, day: int) -> date:
    year = min(max(year, 1970), 2100)
    month = min(max(month, 1), 12)
    return date(year, month, min(max(day, 1), monthrange(year, month)[1]))


def cliff(data: Fields) -> Fields:
    text = string(data.get("start"), "start")
    match = DATE.fullmatch(text.strip())
    if match is None:
        raise ValueError("Use a numeric YYYY-MM-DD start date.")
    year, month, day = (int(value) for value in match.groups())
    start = clamp_date(year, month, day)
    notice = integer(data.get("notice_days"), "notice_days", range(36501))
    term_options = {"term_days", "term_months"}.intersection(data)
    if len(term_options) != 1:
        raise ValueError("Provide term_days or term_months, not both.")
    if "term_months" in term_options:
        term = integer(data["term_months"], "term_months", range(1, 2401))
        offset_year, offset_month = divmod(start.month - 1 + term, 12)
        target_year, target_month = start.year + offset_year, offset_month + 1
        expiration = date(target_year, target_month,
                          min(start.day, monthrange(target_year, target_month)[1]))
    else:
        term = integer(data["term_days"], "term_days", range(1, 73051))
        expiration = start + timedelta(days=term)
    deadline = expiration - timedelta(days=notice)
    return {"start": start.isoformat(), "start_clamped": (year, month, day) !=
            (start.year, start.month, start.day), "expiration": expiration.isoformat(),
            "cliff": deadline.isoformat(),
            "alerts": {str(offset): (deadline - timedelta(days=offset)).isoformat()
                       for offset in (75, 60, 30)}}


def leave(data: Fields) -> Fields:
    source = string(data.get("text"), "text")
    shift = number(data.get("shift_hours", 8), "shift_hours", Decimal("0.01"), 24)
    kind = string(data.get("kind", "planned_pto"), "kind")
    if kind not in ("planned_pto", "statutory_leave"):
        raise ValueError("Use planned_pto or statutory_leave.")
    minimum = Decimal("1.0") if kind == "planned_pto" else Decimal("0.25")
    increment_raw = data.get("usage_increment_hours")
    increment = number(increment_raw, "usage_increment_hours") if increment_raw is not None else None

    count = 0

    def shift_to_hours(amount: Decimal) -> str:
        hours = format(shift * amount, "f")
        if "." in hours:
            hours = hours.rstrip("0").rstrip(".")
        return hours if "." in hours else f"{hours}.0"

    def convert(match: re.Match[str]) -> str:
        nonlocal count
        remainder = source[match.end():]
        if re.match(r"[- ](?:old|long|period|notice)\b", remainder, re.IGNORECASE):
            return match[0]
        count += 1
        amount = Decimal("0.5") if match["half"] else Decimal(match["amount"])
        hours = shift_to_hours(amount)
        if match["start"] is not None:
            join = match["join"] if match["join"].strip().lower() in ("to", "or") else "–"
            hours = f'{shift_to_hours(Decimal(match["start"]))}{join}{hours}'
        period = {"month": " per calendar month", "year": " per year"}.get(
            (match["period"] or "").lower(), "")
        return f"{hours} hours{period}"

    converted = LEAVE.sub(convert, source)
    return {"text": converted, "replacements": count,
            "unresolved_day_units": bool(DAYS.search(converted)),
            "minimum_increment_hours": finite(minimum),
            "increment_valid": increment >= minimum if increment is not None else None}
