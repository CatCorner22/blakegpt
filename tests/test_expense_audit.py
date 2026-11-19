from datetime import date
from decimal import Decimal

from tools.expense_audit import audit_expenses, federal_holidays


def row(
    row_id: str,
    day: str,
    amount: str = "20",
    **values: str,
) -> dict[str, str]:
    return {
        "id": row_id,
        "date": day,
        "employee": values.get("employee", "Employee A"),
        "merchant": values.get("merchant", "Dental Supply"),
        "amount": amount,
        "category": values.get("category", "Supplies"),
        "receipt": values.get("receipt", "receipt.pdf"),
        **({"submitted": values["submitted"]} if "submitted" in values else {}),
    }


def codes(findings) -> set[str]:
    return {finding.code for finding in findings}


def test_split_charges_by_merchant_and_category() -> None:
    findings = audit_expenses(
        [
            row("one", "2026-06-01T09:00:00", "2600"),
            row("two", "2026-06-02T09:00:00", "2500"),
        ]
    )
    assert codes(findings) == {"SPLIT"}
    assert {finding.row_id for finding in findings} == {"one", "two"}


def test_duplicate_transaction_key() -> None:
    findings = audit_expenses(
        [
            row("one", "2026-06-01", "20"),
            row("two", "2026-06-01", "20"),
        ]
    )
    assert codes(findings) == {"DUPLICATE"}


def test_duplicate_receipt_content(tmp_path) -> None:
    (tmp_path / "first.pdf").write_bytes(b"same receipt")
    (tmp_path / "second.pdf").write_bytes(b"same receipt")
    findings = audit_expenses(
        [
            row("one", "2026-06-01", "20", receipt="first.pdf"),
            row("two", "2026-06-02", "21", receipt="second.pdf"),
        ],
        base_dir=tmp_path,
    )
    assert codes(findings) == {"DUPLICATE"}


def test_weekend_flag() -> None:
    findings = audit_expenses([row("weekend", "2026-07-05", "20")])
    assert "WEEKEND" in codes(findings)


def test_federal_holiday_observation_and_thanksgiving() -> None:
    holidays = federal_holidays(2026)
    assert date(2026, 7, 3) in holidays
    assert date(2026, 7, 4) in holidays
    assert date(2026, 11, 26) in holidays
    findings = audit_expenses([row("observed", "2026-07-03", "20")])
    assert "HOLIDAY" in codes(findings)


def test_no_receipt_flag() -> None:
    findings = audit_expenses([row("missing", "2026-06-01", "75", receipt="")])
    assert "NO-RECEIPT" in codes(findings)


def test_late_submission_flag() -> None:
    findings = audit_expenses(
        [row("late", "2026-01-01", "20", submitted="2026-02-01")]
    )
    assert "LATE" in codes(findings)


def test_clean_expense_has_no_findings() -> None:
    findings = audit_expenses(
        [row("clean", "2026-06-01", "20", submitted="2026-06-10")]
    )
    assert findings == []


def test_threshold_arguments_accept_decimal_values() -> None:
    findings = audit_expenses(
        [row("small", "2026-06-01", "50")],
        threshold=Decimal("5000"),
    )
    assert findings == []
