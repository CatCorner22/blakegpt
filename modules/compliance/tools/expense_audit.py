from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class ExpenseFinding:
    row_id: str
    code: str
    message: str


def _amount(value: str | Decimal) -> Decimal:
    try:
        amount = value if isinstance(value, Decimal) else Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"invalid amount: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError("amounts must be finite")
    return amount


def parse_datetime(value: str) -> datetime:
    clean = value.strip()
    try:
        parsed = datetime.fromisoformat(clean.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.combine(date.fromisoformat(clean), time.min)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last = next_month - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def federal_holidays(year: int) -> set[date]:
    observed: set[date] = set()
    for holiday_year in (year - 1, year, year + 1):
        fixed = (
            (1, 1),
            (6, 19),
            (7, 4),
            (11, 11),
            (12, 25),
        )
        for month, day in fixed:
            statutory_date = date(holiday_year, month, day)
            observed.update({statutory_date, _observed(statutory_date)})
        observed.update(
            {
                _nth_weekday(holiday_year, 1, 0, 3),
                _nth_weekday(holiday_year, 2, 0, 3),
                _last_weekday(holiday_year, 5, 0),
                _nth_weekday(holiday_year, 9, 0, 1),
                _nth_weekday(holiday_year, 10, 0, 2),
                _nth_weekday(holiday_year, 11, 3, 4),
            }
        )
    return {holiday for holiday in observed if holiday.year == year}


def _csv_date(value: str) -> date:
    return parse_datetime(value).date()


def audit_expenses(
    rows: list[dict[str, str]],
    threshold: Decimal | str | float = Decimal("5000"),
    window_hours: int | float = 72,
    receipt_threshold: Decimal | str | float = Decimal("75"),
    late_days: int = 30,
    base_dir: Path | None = None,
) -> list[ExpenseFinding]:
    split_threshold = _amount(str(threshold))
    receipt_minimum = _amount(str(receipt_threshold))
    if split_threshold < 0 or receipt_minimum < 0 or window_hours < 0 or late_days < 0:
        raise ValueError("thresholds, window_hours, and late_days must not be negative")
    window = timedelta(hours=float(window_hours))
    root = base_dir or Path.cwd()
    findings: set[ExpenseFinding] = set()
    enriched: list[dict[str, object]] = []

    for row in rows:
        if "id" not in row or "date" not in row or "amount" not in row:
            raise ValueError("expense rows require id, date, and amount")
        entry: dict[str, object] = dict(row)
        entry["amount_decimal"] = _amount(row["amount"])
        entry["datetime"] = parse_datetime(row["date"])
        entry["date_only"] = _csv_date(row["date"])
        enriched.append(entry)

    def mark(entry: dict[str, object], code: str, message: str) -> None:
        findings.add(ExpenseFinding(str(entry["id"]), code, message))

    for entry in enriched:
        day = entry["date_only"]
        assert isinstance(day, date)
        if day.weekday() >= 5:
            mark(entry, "WEEKEND", "Charge date falls on a weekend.")
        if day in federal_holidays(day.year):
            mark(entry, "HOLIDAY", "Charge date falls on a US federal holiday.")
        if entry["amount_decimal"] >= receipt_minimum and not str(
            entry.get("receipt", "")
        ).strip():
            mark(entry, "NO-RECEIPT", "Receipt is missing for a charge at or above the threshold.")
        submitted = str(entry.get("submitted", "")).strip()
        if submitted:
            delay = (_csv_date(submitted) - day).days
            if delay > late_days:
                mark(entry, "LATE", f"Submitted {delay} days after the charge date.")

    duplicate_keys: dict[tuple[object, ...], list[dict[str, object]]] = {}
    receipt_hashes: dict[str, list[dict[str, object]]] = {}
    for entry in enriched:
        employee = str(entry.get("employee", "")).strip().casefold()
        merchant = str(entry.get("merchant", "")).strip().casefold()
        if employee and merchant:
            duplicate_key = (
                employee,
                merchant,
                entry["amount_decimal"],
                entry["date_only"],
            )
            duplicate_keys.setdefault(duplicate_key, []).append(entry)
        receipt = str(entry.get("receipt", "")).strip()
        if receipt:
            path = Path(receipt)
            if not path.is_absolute():
                path = root / path
            if path.is_file():
                with path.open("rb") as source:
                    digest = hashlib.file_digest(source, "sha256").hexdigest()
                receipt_hashes.setdefault(digest, []).append(entry)
    for group in duplicate_keys.values():
        if len(group) > 1:
            for entry in group:
                mark(entry, "DUPLICATE", "Same employee, merchant, amount, and date appears more than once.")
    for group in receipt_hashes.values():
        if len(group) > 1:
            for entry in group:
                mark(entry, "DUPLICATE", "Receipt file content matches another row.")

    groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for entry in enriched:
        employee = str(entry.get("employee", "")).casefold()
        merchant = str(entry.get("merchant", "")).strip().casefold()
        category = str(entry.get("category", "")).strip().casefold()
        if merchant:
            groups.setdefault(("merchant", employee, merchant), []).append(entry)
        if category:
            groups.setdefault(("category", employee, category), []).append(entry)
    for group in groups.values():
        candidates = [
            entry
            for entry in group
            if entry["amount_decimal"] < split_threshold
        ]
        candidates.sort(key=lambda entry: entry["datetime"])
        for start in range(len(candidates)):
            total = Decimal("0")
            start_time = candidates[start]["datetime"]
            for end in range(start, len(candidates)):
                current = candidates[end]
                if current["datetime"] - start_time > window:
                    break
                total += current["amount_decimal"]
                if end > start and total >= split_threshold:
                    for involved in candidates[start : end + 1]:
                        mark(involved, "SPLIT", "Multiple below-threshold charges reach the threshold within the window.")

    return sorted(findings, key=lambda item: (item.row_id, item.code, item.message))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit expense CSV rows.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--threshold", type=Decimal, default=Decimal("5000"))
    parser.add_argument("--window-hours", type=float, default=72)
    parser.add_argument("--receipt-threshold", type=Decimal, default=Decimal("75"))
    parser.add_argument("--late-days", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    findings = audit_expenses(
        _read_csv(args.file),
        args.threshold,
        args.window_hours,
        args.receipt_threshold,
        args.late_days,
        args.file.parent,
    )
    if args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2))
    elif findings:
        for item in findings:
            print(f"{item.row_id} {item.code}: {item.message}")
    else:
        print("No findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
