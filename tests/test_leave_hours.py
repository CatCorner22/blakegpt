from decimal import Decimal

import pytest

from tools.leave_hours import accrue, main, year_end_carryover


def run_accrual(
    worked: list[str],
    *,
    rate: str = "30",
    annual_cap: str | None = None,
    balance_cap: str | None = None,
    carryover_cap: str | None = None,
    starting: str = "0",
    used: list[str] | None = None,
    waiting: str = "0",
):
    return accrue(
        worked,
        rate,
        annual_cap,
        balance_cap,
        carryover_cap,
        starting,
        used or ["0"] * len(worked),
        waiting,
    )


def test_one_hour_per_thirty_hours() -> None:
    assert run_accrual(["30"])[0].earned == Decimal("1.00")


def test_one_hour_per_forty_hours() -> None:
    assert run_accrual(["40"], rate="40")[0].earned == Decimal("1.00")


def test_annual_cap_stops_accrual_during_period() -> None:
    rows = run_accrual(["80", "80"], rate="40", annual_cap="3")
    assert [row.earned for row in rows] == [Decimal("2.00"), Decimal("1.00")]


def test_annual_cap_resets_at_plan_year_start() -> None:
    rows = accrue(
        ["40", "40"],
        "40",
        "1",
        None,
        None,
        "0",
        ["0", "0"],
        periods=["2025-12-31", "2026-01-31"],
        year_start="01-01",
    )
    assert [row.earned for row in rows] == [Decimal("1.00"), Decimal("1.00")]


def test_cli_accepts_year_start_option(tmp_path, monkeypatch, capsys) -> None:
    source = tmp_path / "hours.csv"
    source.write_text(
        "period,hours_worked,hours_used\n"
        "2025-06-30,40,0\n"
        "2025-07-31,40,0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["leave_hours", str(source), "--rate", "40", "--annual-cap", "1", "--year-start", "07-01"],
    )

    assert main() == 0
    assert capsys.readouterr().out.splitlines()[1:] == [
        "2025-06-30,40,1.00,0,1.00",
        "2025-07-31,40,1.00,0,2.00",
    ]


def test_balance_cap_limits_accrual() -> None:
    rows = run_accrual(["80"], rate="40", balance_cap="5", starting="4")
    assert rows[0].earned == Decimal("1.00")
    assert rows[0].balance == Decimal("5.00")


def test_waiting_period_counts_hours_before_earning() -> None:
    rows = run_accrual(["40", "50"], rate="10", waiting="50")
    assert [row.earned for row in rows] == [Decimal("0.00"), Decimal("4.00")]


def test_carryover_cap() -> None:
    assert year_end_carryover("45.25", "40") == Decimal("40.00")
    assert year_end_carryover("45.25", None) == Decimal("45.25")
    rows = run_accrual(["80"], rate="40", carryover_cap="1")
    assert rows[-1].balance == Decimal("1.00")


def test_rounding_uses_half_up_per_period() -> None:
    assert run_accrual(["1"], rate="8")[0].earned == Decimal("0.13")


def test_usage_cannot_exceed_available_balance() -> None:
    with pytest.raises(ValueError, match="usage exceeds available balance"):
        run_accrual(["0"], used=["0.01"])
