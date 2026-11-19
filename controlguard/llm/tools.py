from decimal import Decimal

from controlguard.app import ENGINES
from controlguard.inputs import Fields, fields, items, string
from controlguard.risk import ASSETS, GATES, VERTICES

SYSTEM = ("You route requests to ControlGuard tools. Extract facts the user states. Never calculate or guess. "
          "If the user supplies the facts, call a tool before returning any status. "
          "For a policy draft, use short, active sentences with must, may or must not; call policy to screen it. "
          "After a tool responds, return {\"status\":\"complete\"}. "
          "If you need facts the user did not provide, return {\"status\":\"needs_input\"}.")


def shape(properties: Fields, *required: str) -> Fields:
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


def scalar(kind: str) -> Fields:
    return {"type": kind}


def choice(*values: str) -> Fields:
    return {"type": "string", "enum": list(values)}


TEXT = scalar("string")
NUM = scalar("number")
INT = scalar("integer")
BOOL = scalar("boolean")
SCHEMAS = {
    "policy": shape({"title": TEXT, "text": TEXT, "kind": choice("policy", "contract")}, "text"),
    "leave": shape({"text": TEXT, "shift_hours": NUM, "kind": choice("planned_pto", "statutory_leave"),
                    "usage_increment_hours": NUM}, "text"),
    "sod": shape({"subject": TEXT, "asset_class": choice(*ASSETS),
                  "vertices": {"type": "array", "items": choice(*VERTICES)},
                  "impact": NUM, "exploitability": NUM}, "subject", "asset_class", "vertices"),
    "triage": shape({"gates": shape({key: BOOL for key in GATES}, *GATES),
                     **{key: INT for key in ("impact", "likelihood", "legal", "detection",
                                             "recoverability", "aggregation")}}, "gates"),
    "price": shape({key: NUM for key in ("quantity", "invoice_pack", "po_pack", "billed_price",
                                        "contract_list_price", "discount")},
                   "quantity", "invoice_pack", "po_pack", "billed_price", "contract_list_price", "discount"),
    "skim": shape({"tolerance": NUM, "invoices": {"type": "array", "items":
                   shape({"invoice_unit_price": NUM, "po_unit_price": NUM},
                         "invoice_unit_price", "po_unit_price")}}, "tolerance", "invoices"),
}
ADAPTERS = {"a1": ("policy", "leave"), "a2": ("sod", "triage", "price", "skim")}
FINAL = shape({"status": choice("complete", "needs_input")}, "status")


def tools_for(names: tuple[str, ...]) -> list[Fields]:
    return [{"type": "function", "function": {"name": name, "description": ENGINES[name].help,
                                             "parameters": SCHEMAS[name]}} for name in names]


def validate(value: object, schema: Fields, label: str = "arguments") -> None:
    kind = schema["type"]
    if kind == "object":
        obj = fields(value, label)
        properties = fields(schema["properties"])
        required = [string(key, label) for key in items(schema["required"], label)]
        if any(key not in obj for key in required) or set(obj).difference(properties):
            raise ValueError(f"{label} has missing or unexpected fields.")
        for key, child in obj.items():
            validate(child, fields(properties[key]), f"{label}.{key}")
    elif kind == "array":
        for child in items(value, label):
            validate(child, fields(schema["items"]), label)
    elif kind == "string":
        string(value, label)
        if "enum" in schema and value not in items(schema["enum"], label):
            raise ValueError(f"{label} is outside its allowed values.")
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} needs an integer.")
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError(f"{label} needs a number.")
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{label} needs true or false.")
    else:
        raise ValueError("Unsupported tool schema.")
