from dataclasses import dataclass
from decimal import DecimalException
from importlib.resources import files

from .calendar_leave import cliff, leave
from .inputs import Fields, decode, string
from .ledger import Ledger
from .policy import handbook, policy
from .pricing import price, skim
from .risk import sod, triage
from .rules import review_rules

DISCLAIMER = ("Use these findings to guide review. They do not provide legal advice, "
              "an audit opinion or a CPA attestation.")


@dataclass(frozen=True)
class Engine:
    title: str
    help: str
    example: Fields


ENGINES = {
    "triage": Engine("Triage a finding", "Check the four gates and score one control finding.", {
        "gates": {"personal_statutory_liability": False, "irreversible_money_out": False,
                  "ability_to_operate": False, "active_incident": False},
        "impact": 4, "likelihood": 3, "legal": 2, "detection": 2, "recoverability": 0,
        "aggregation": 0,
    }),
    "sod": Engine("Check duty conflicts", "Score one person or vendor for one asset class.", {
        "subject": "example-role", "asset_class": "Payables",
        "vertices": ["authorization", "custody"], "impact": 9, "exploitability": 8,
    }),
    "price": Engine("Check an invoice price", "Compare the billed price with the contract price.", {
        "quantity": 4, "invoice_pack": 6, "po_pack": 12, "billed_price": 30,
        "contract_list_price": 60, "discount": 0.2,
    }),
    "skim": Engine("Check the PO tolerance", "Compare one vendor's invoices with their PO prices.", {
        "tolerance": 0.05, "invoices": [{"invoice_unit_price": value, "po_unit_price": 100}
                                       for value in (104.5, 104.6, 104.9, 100)],
    }),
    "cliff": Engine("Find a notice deadline", "Set the start, term and notice window.", {
        "start": "2026-01-31", "term_months": 12, "notice_days": 60,
    }),
    "leave": Engine("Convert leave to hours", "Enter only shift-based leave text.", {
        "text": "Staff earn 1 day/month and can take a half-day.", "shift_hours": 8,
    }),
    "policy": Engine("Screen policy wording", "Check the title and the wording the spec lists.", {
        "title": "Policy: Human Resources--Benefits.  HR Policy 4",
        "text": "The manager shall document each request.", "kind": "policy",
    }),
    "handbook": Engine("Check handbook safeguards", "Enter facts you confirmed. Omit unknowns.", {
        "jurisdiction": "MT", "facts": {"front_noncontract_disclaimer": True,
                                      "receipt_and_reading_only": True},
    }),
    "rules": Engine("Flag pricing practices", "Enter the contract or invoice facts you confirmed.", {
        "facts": {"unanchored_list_discount": True},
    }),
    "ledger": Engine("Review the sign-off ledger", "Verify the chain or add a named sign-off.", {
        "action": "verify",
    }),
    "catalog": Engine("Browse the control catalogs", "Choose C, DEF, O, TW, CON, FT, RULE or INV-TRAP.", {
        "catalog": "C",
    }),
}


def ledger_operation(data: Fields, ledger: Ledger) -> Fields:
    action = data.get("action")
    if action == "verify":
        entries = ledger.verify()
        return {"valid": True, "count": len(entries), "head": entries[-1]["hash"] if entries else None,
                "records": entries}
    if action == "append":
        return ledger.append(
            subject=string(data.get("subject"), "subject"), control=string(data.get("control"), "control"),
            signer=string(data.get("signer"), "signer"), actor=string(data.get("actor"), "actor"),
            cadence=string(data.get("cadence"), "cadence"), artifact=string(data.get("artifact"), "artifact"),
        )
    raise ValueError("Use verify or append.")


def catalog(data: Fields) -> Fields:
    catalogs = decode(files("controlguard").joinpath("catalogs.json").read_text(encoding="utf-8"))
    name = string(data.get("catalog"), "catalog")
    if name not in catalogs:
        raise ValueError("Select a listed catalog.")
    return {"catalog": name, "entries": catalogs[name],
            "basis": "Spec reference material. Verify legal and numerical claims before using them."}


def run_engine(engine: str, data: Fields, ledger: Ledger) -> Fields:
    try:
        if engine == "triage":
            result = triage(data, ledger)
        elif engine == "sod":
            result = sod(data, ledger)
        elif engine == "ledger":
            result = ledger_operation(data, ledger)
        else:
            functions = {"price": price, "skim": skim, "cliff": cliff, "leave": leave, "policy": policy,
                         "handbook": handbook, "rules": review_rules, "catalog": catalog}
            if engine not in functions:
                raise ValueError("Select a listed tool.")
            result = functions[engine](data)
    except (DecimalException, OverflowError) as error:
        raise ValueError("The calculation exceeds the supported numerical range.") from error
    return {**result, "disclaimer": DISCLAIMER}
