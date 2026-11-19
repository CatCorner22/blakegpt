from datetime import datetime
from decimal import Decimal

from .inputs import Fields, boolean, fields, finite, integer, items, number, string
from .ledger import Ledger

GATES = ("personal_statutory_liability", "irreversible_money_out",
         "ability_to_operate", "active_incident")
PROOFS = ("compensating_has_actor", "compensating_has_cadence", "compensating_has_artifact")
ASSETS = ("Cash", "Payables", "Payroll", "Controlled Substances",
          "Surgical Implants", "Inventory", "DNS/IT")
VERTICES = ("authorization", "custody", "recordkeeping", "reconciliation")


def evidence(data: Fields, ledger: Ledger, now: datetime | None) -> tuple[str, str | None]:
    proofs = [boolean(data.get(key, False), key) for key in PROOFS]
    if not all(proofs):
        return "missing_triple_proof", None
    subject = data.get("subject")
    control = data.get("control")
    if subject is None or control is None:
        return "no_signoff", None
    return ledger.status(string(subject, "subject"), string(control, "control"), now)


def triage(data: Fields, ledger: Ledger, now: datetime | None = None) -> Fields:
    gates = fields(data.get("gates"), "gates")
    if set(gates) != set(GATES):
        raise ValueError("Provide all four named gates, and no others.")
    active = [key for key in GATES if boolean(gates[key], key)]
    if active:
        return {"tier": 1, "triggered_gates": active, "score": None,
                "permanent_fix_days": 30, "interim_control_days": 7}
    impact = integer(data.get("impact"), "impact", range(1, 6))
    likelihood = integer(data.get("likelihood"), "likelihood", range(1, 6))
    legal = integer(data.get("legal"), "legal", (0, 2, 4, 6))
    detection = integer(data.get("detection"), "detection", (0, 2, 3))
    recoverability = integer(data.get("recoverability"), "recoverability", (0, 2, 3))
    requested = integer(data.get("compensating_credit", 0), "compensating_credit", range(4))
    aggregation = integer(data.get("aggregation"), "aggregation", (0, 2))
    status, signed_at = evidence(data, ledger, now) if requested else ("not_requested", None)
    credit = requested if status == "active" else 0
    score = impact * likelihood + legal + detection + recoverability - credit + aggregation
    tier = 1 if score >= 24 else 2 if score >= 16 else 3 if score >= 9 else 4
    result: Fields = {"tier": tier, "score": score, "triggered_gates": [],
                      "compensating_credit": credit, "proof_status": status, "signed_at": signed_at}
    if tier == 1:
        result.update(permanent_fix_days=30, interim_control_days=7)
    if requested and not credit:
        result["warning"] = "Verify the reviewer, cadence and audit artifact before relying on this control."
    return result


def sod(data: Fields, ledger: Ledger, now: datetime | None = None) -> Fields:
    subject = string(data.get("subject"), "subject")
    asset = string(data.get("asset_class"), "asset_class")
    if asset not in ASSETS:
        raise ValueError("Select a listed asset class.")
    raw = items(data.get("vertices"), "vertices")
    vertices = {string(value, "vertex") for value in raw}
    if not vertices.issubset(VERTICES):
        raise ValueError("Use authorization, custody, recordkeeping or reconciliation.")
    result: Fields = {"subject": subject, "asset_class": asset,
                      "vertices": [vertex for vertex in VERTICES if vertex in vertices],
                      "conflict": len(vertices) >= 2}
    if len(vertices) < 2:
        return {**result, "priority": None, "score": None}
    impact = number(data.get("impact"), "impact", 1, 10)
    exploitability = number(data.get("exploitability"), "exploitability", 1, 10)
    requested = number(data.get("factor", 1), "factor", Decimal("0.15"), 1)
    status, signed_at = evidence(data, ledger, now) if requested < 1 else ("not_requested", None)
    factor = requested if status == "active" else Decimal(1)
    score = impact * exploitability * factor
    priority = "P1" if score >= 60 else "P2" if score >= 35 else "P3" if score >= 15 else "P4"
    return {**result, "priority": priority, "score": finite(score),
            "remediation_hours": {"P1": 48, "P2": 336}.get(priority),
            "next_step": {"P1": "Remediate now.", "P2": "Remediate within 14 calendar days.",
                          "P3": "Monitor weekly or monthly.", "P4": "Review annually."}[priority],
            "factor": finite(factor), "proof_status": status, "signed_at": signed_at}
