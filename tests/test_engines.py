from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from controlguard.app import ENGINES, run_engine
from controlguard.inputs import decode, encode
from controlguard.ledger import Ledger
from controlguard.risk import GATES, PROOFS, sod, triage

NOW = datetime(2026, 11, 13, 18, tzinfo=timezone.utc)


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path / "test.sqlite3")


@pytest.mark.parametrize("gate", GATES)
def test_any_gate_short_circuits(gate: str, ledger: Ledger) -> None:
    result = triage({"gates": {key: key == gate for key in GATES}}, ledger)
    assert (result["tier"], result["score"], result["permanent_fix_days"],
            result["interim_control_days"]) == (1, None, 30, 7)


@pytest.mark.parametrize(("impact", "likelihood", "legal", "expected"), [
    (4, 5, 4, 1), (4, 5, 2, 2), (4, 4, 0, 2), (5, 3, 0, 3),
    (3, 3, 0, 3), (4, 2, 0, 4),
])
def test_triage_tiers(impact: int, likelihood: int, legal: int, expected: int, ledger: Ledger) -> None:
    result = triage({**ENGINES["triage"].example, "impact": impact, "likelihood": likelihood,
                     "legal": legal, "detection": 0}, ledger)
    assert result["tier"] == expected


def sign(ledger: Ledger, subject: str = "example-role", control: str = "C4") -> None:
    ledger.append(subject=subject, control=control, signer="Owner", actor="Reviewer",
                  cadence="Weekly", artifact="Signed exception log", now=NOW)


def test_triage_credit_requires_all_proofs_and_a_current_scoped_record(ledger: Ledger) -> None:
    data = {**ENGINES["triage"].example, "compensating_credit": 3, "recoverability": 3,
            "aggregation": 2, "subject": "example-role", "control": "C4"}
    data.update({key: True for key in PROOFS})
    assert triage(data, ledger, NOW)["score"] == 21
    sign(ledger, control="C5")
    assert triage(data, ledger, NOW)["compensating_credit"] == 0
    sign(ledger)
    for key in PROOFS:
        assert triage({**data, key: False}, ledger, NOW)["compensating_credit"] == 0
    assert triage(data, ledger, NOW)["score"] == 18
    assert triage(data, ledger, NOW + timedelta(hours=336))["compensating_credit"] == 0


def test_sod_lapse_recomputes_and_does_not_force_p1(ledger: Ledger) -> None:
    data = {**ENGINES["sod"].example, "impact": 5, "exploitability": 4,
            "factor": Decimal("0.5"), "control": "C4"}
    data.update({key: True for key in PROOFS})
    sign(ledger)
    assert sod(data, ledger, NOW + timedelta(hours=336, microseconds=-1))["priority"] == "P4"
    result = sod(data, ledger, NOW + timedelta(hours=336))
    assert (result["priority"], result["factor"], result["score"], result["proof_status"]) == (
        "P3", 1.0, 20, "lapsed")
    assert sod({**data, "vertices": ["custody", "custody"]}, ledger, NOW)["conflict"] is False


@pytest.mark.parametrize(("impact", "exploitability", "priority"), [
    (6, 10, "P1"), (Decimal("5.995"), 10, "P2"), (5, 7, "P2"),
    (Decimal("3.495"), 10, "P3"), (3, 5, "P3"), (2, 7, "P4"),
])
def test_sod_bands(impact: Decimal | int, exploitability: int, priority: str, ledger: Ledger) -> None:
    assert sod({**ENGINES["sod"].example, "impact": impact, "exploitability": exploitability},
               ledger)["priority"] == priority


def test_ledger_verifies_links_and_detects_modified_content(ledger: Ledger) -> None:
    sign(ledger)
    sign(ledger, control="C6")
    records = ledger.verify()
    assert len(records) == 2
    assert records[1]["prior_hash"] == records[0]["hash"]
    with sqlite3.connect(ledger.path) as conn:
        conn.execute("UPDATE attestations SET signer = 'Changed' WHERE seq = 1")
    with pytest.raises(ValueError, match="verification failed"):
        ledger.verify()


def test_price_formulas_and_pack_edge(ledger: Ledger) -> None:
    data = ENGINES["price"].example
    result = run_engine("price", data, ledger)
    assert (result["invoice_unit_price"], result["truth_unit_price"],
            result["truth_total"], result["overcharge"]) == (5, 4, 96, 24)
    assert result["flags"] == ["INV-TRAP-04"]
    assert run_engine("price", {**data, "billed_price": 1}, ledger)["overcharge"] == 0
    zero = run_engine("price", {**data, "invoice_pack": 0, "po_pack": 0}, ledger)
    assert zero["warnings"] and zero["truth_total"] == 0
    assert zero["warnings"] == ["A pack size is zero or too small. Check the pack sizes before using this amount."]
    with pytest.raises(ValueError, match="finite"):
        run_engine("price", {**data, "quantity": Decimal("1e500")}, ledger)


def test_skew_edges(ledger: Ledger) -> None:
    prices = [103] * 5 + [105] * 2 + [100] * 3
    invoices = [{"invoice_unit_price": price, "po_unit_price": 100} for price in prices]
    result = run_engine("skim", {"invoices": invoices, "tolerance": 0.05}, ledger)
    assert (result["flagged"], result["positive_skew"], result["ceiling_hug"]) == (True, .7, .5)
    assert run_engine("skim", {"invoices": invoices[:3], "tolerance": 0.05}, ledger)["flagged"] is False
    assert run_engine("skim", {"invoices": [], "tolerance": 0}, ledger)["positive_skew"] is None
    with pytest.raises(ValueError, match="undefined"):
        run_engine("skim", {"tolerance": .05, "invoices": [{"invoice_unit_price": 1, "po_unit_price": 0}]}, ledger)


def test_cliff_and_clamping(ledger: Ledger) -> None:
    result = run_engine("cliff", {"start": "2024-01-32", "term_months": 1, "notice_days": 30}, ledger)
    assert (result["start"], result["expiration"], result["cliff"]) == ("2024-01-31", "2024-02-29", "2024-01-30")
    assert result["alerts"] == {"75": "2023-11-16", "60": "2023-12-01", "30": "2023-12-31"}
    assert run_engine("cliff", {"start": "1000-13-99", "term_days": 1, "notice_days": 0},
                      ledger)["expiration"] == "1971-01-01"
    with pytest.raises(ValueError, match="numeric"):
        run_engine("cliff", {"start": "next Tuesday", "term_days": 10, "notice_days": 0}, ledger)


def test_leave_baseline_increments_and_calendar_text(ledger: Ledger) -> None:
    result = run_engine("leave", {"text": "Earn 1 day/month, cap 12 days/year, take a half-day."}, ledger)
    assert result["text"] == "Earn 8.0 hours per calendar month, cap 96.0 hours per year, take 4.0 hours."
    result = run_engine("leave", {"text": "Take a half-day within 5 business days.", "shift_hours": 6,
                                  "kind": "statutory_leave", "usage_increment_hours": .25}, ledger)
    assert result["text"] == "Take 3.0 hours within 5 business days."
    assert result["increment_valid"] is True and result["unresolved_day_units"] is True
    assert run_engine("leave", {"text": "Use leave.", "usage_increment_hours": .25},
                      ledger)["increment_valid"] is False


@pytest.mark.parametrize(("source", "expected"), [
    ("1–2 days", "8.0–16.0 hours"),
    ("1-2 days", "8.0–16.0 hours"),
    ("1 to 2 days", "8.0 to 16.0 hours"),
    ("1 or 2 days", "8.0 or 16.0 hours"),
    ("0.5 – 2 days/month", "4.0–16.0 hours per calendar month"),
])
def test_leave_converts_both_endpoints(ledger: Ledger, source: str, expected: str) -> None:
    result = run_engine("leave", {"text": source}, ledger)
    assert result["text"] == expected
    assert result["replacements"] == 1
    assert result["unresolved_day_units"] is False


def test_leave_keeps_notice_ranges(ledger: Ledger) -> None:
    result = run_engine("leave", {"text": "Give 1–2 days notice."}, ledger)
    assert result["text"] == "Give 1–2 days notice."
    assert result["unresolved_day_units"] is True


def test_policy_guardrails_rules_and_catalog(ledger: Ledger) -> None:
    titles = ["Policy: Human Resources--Benefits.  HR Policy 4",
              "Policy: Information Technology--Digital Asset Custody.  IT Policy 2"]
    for title in titles:
        assert run_engine("policy", {"title": title, "text": "Staff must file a form."}, ledger)["passes_screen"]
    result = run_engine("policy", {"title": titles[0].replace("Benefits", "Workers' Benefits"),
                                   "text": "Staff SHALL act promptly."},
                        ledger)
    assert result["title_valid"] is False
    assert result["flags"] == [{"term": "SHALL", "offset": 6, "suggestion": "must, if this is a duty", "review": False},
                               {"term": "promptly", "offset": 16, "suggestion": None, "review": False}]
    handbook = run_engine("handbook", {"jurisdiction": "MT", "facts": {}}, ledger)
    assert "HR-GUARD-01-MT" in encode(handbook)
    rules = run_engine("rules", {"facts": {"unanchored_list_discount": True}}, ledger)
    assert rules["flags"] == ["RULE-01"] and "gag_clause_confirmed_prohibited" in encode(rules["fact_keys"])
    assert "FT-16" in encode(run_engine("catalog", {"catalog": "FT"}, ledger))


def test_strict_json_and_cli_round_trip(ledger: Ledger) -> None:
    for invalid in ('{"value":NaN}', '{"x":1,"x":2}', '[]', '{"x":1e' + '9' * 32 + '}'):
        with pytest.raises(ValueError):
            decode(invalid)
    with pytest.raises(ValueError):
        encode({"value": float("inf")})
    command = [sys.executable, "-m", "controlguard", "--ledger", str(ledger.path), "run", "price"]
    result = subprocess.run(command, input=encode(ENGINES["price"].example), text=True,
                            capture_output=True, check=True)
    assert decode(result.stdout)["overcharge"] == 24
