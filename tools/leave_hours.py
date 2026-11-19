from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path


CENT = Decimal("0.01")


def _decimal(value: float | int | str | Decimal) -> Decimal:
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal value: {value!r}") from exc
    if not number.is_finite():
        raise ValueError("hours and rates must be finite numbers")
    return number


def _round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _capped_round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_DOWN)


@dataclass(frozen=True)
class PeriodRow:
    period: str
    worked: Decimal
    earned: Decimal
    used: Decimal
    balance: Decimal


def accrue(
    hours_worked: list[float | int | str | Decimal],
    rate_hours_worked_per_hour_earned: float | int | str | Decimal,
    annual_cap_hours: float | int | str | Decimal | None,
    balance_cap_hours: float | int | str | Decimal | None,
    carryover_cap_hours: float | int | str | Decimal | None,
    starting_balance: float | int | str | Decimal,
    used: list[float | int | str | Decimal],
    waiting_period_hours: float | int | str | Decimal = 0,
    periods: list[str] | None = None,
) -> list[PeriodRow]:
    worked_values = [_decimal(value) for value in hours_worked]
    used_values = [_decimal(value) for value in used]
    if len(worked_values) != len(used_values):
        raise ValueError("hours_worked and used must have the same number of periods")
    rate = _decimal(rate_hours_worked_per_hour_earned)
    if rate <= 0:
        raise ValueError("rate_hours_worked_per_hour_earned must be greater than zero")
    annual_cap = None if annual_cap_hours is None else _decimal(annual_cap_hours)
    balance_cap = None if balance_cap_hours is None else _decimal(balance_cap_hours)
    carryover_cap = None if carryover_cap_hours is None else _decimal(carryover_cap_hours)
    balance = _round(_decimal(starting_balance))
    waiting_remaining = _decimal(waiting_period_hours)
    for cap in (annual_cap, balance_cap, carryover_cap):
        if cap is not None and cap < 0:
            raise ValueError("caps must not be negative")
    if waiting_remaining < 0 or balance < 0:
        raise ValueError("waiting period and starting balance must not be negative")
    if balance_cap is not None and balance > balance_cap:
        raise ValueError("starting balance exceeds the balance cap")
    if periods is not None and len(periods) != len(worked_values):
        raise ValueError("periods must have the same number of entries as hours_worked")

    annual_earned = Decimal("0")
    rows: list[PeriodRow] = []
    for index, (worked, period_used) in enumerate(zip(worked_values, used_values), 1):
        if worked < 0 or period_used < 0:
            raise ValueError("worked and used hours must not be negative")
        eligible_worked = max(Decimal("0"), worked - waiting_remaining)
        waiting_remaining = max(Decimal("0"), waiting_remaining - worked)
        earned = _round(eligible_worked / rate)
        if annual_cap is not None:
            remaining_annual = max(Decimal("0"), annual_cap - annual_earned)
            if earned > remaining_annual:
                earned = _capped_round(remaining_annual)
        if balance_cap is not None:
            remaining_balance = max(Decimal("0"), balance_cap - balance)
            if earned > remaining_balance:
                earned = _capped_round(remaining_balance)
        if period_used > balance + earned:
            raise ValueError(f"usage exceeds available balance in period {index}")
        balance = _round(balance + earned - period_used)
        annual_earned += earned
        rows.append(
            PeriodRow(
                periods[index - 1] if periods else str(index),
                worked,
                earned,
                period_used,
                balance,
            )
        )
    if rows and carryover_cap is not None:
        rows[-1] = PeriodRow(
            rows[-1].period,
            rows[-1].worked,
            rows[-1].earned,
            rows[-1].used,
            year_end_carryover(balance, carryover_cap),
        )
    return rows


def year_end_carryover(
    balance: float | int | str | Decimal,
    carryover_cap: float | int | str | Decimal | None,
) -> Decimal:
    current = _decimal(balance)
    if current < 0:
        raise ValueError("balance must not be negative")
    if carryover_cap is None:
        return _round(current)
    cap = _decimal(carryover_cap)
    if cap < 0:
        raise ValueError("carryover cap must not be negative")
    if current > cap:
        return _capped_round(cap)
    return _round(current)


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate policy-driven leave accrual.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--rate", type=Decimal, required=True, help="hours worked per earned hour")
    parser.add_argument("--annual-cap", type=Decimal)
    parser.add_argument("--balance-cap", type=Decimal)
    parser.add_argument("--carryover-cap", type=Decimal)
    parser.add_argument("--starting-balance", type=Decimal, default=Decimal("0"))
    parser.add_argument("--waiting-period-hours", type=Decimal, default=Decimal("0"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    with args.file.open(newline="", encoding="utf-8") as source:
        records = list(csv.DictReader(source))
    rows = accrue(
        [record["hours_worked"] for record in records],
        args.rate,
        args.annual_cap,
        args.balance_cap,
        args.carryover_cap,
        args.starting_balance,
        [record["hours_used"] for record in records],
        args.waiting_period_hours,
        [record["period"] for record in records],
    )
    result = [asdict(row) for row in rows]
    if args.json:
        print(
            json.dumps(
                [
                    {
                        **item,
                        **{
                            key: str(value)
                            for key, value in item.items()
                            if isinstance(value, Decimal)
                        },
                    }
                    for item in result
                ],
                indent=2,
            )
        )
    else:
        print("period,worked,earned,used,balance")
        for row in rows:
            print(f"{row.period},{row.worked},{row.earned},{row.used},{row.balance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
