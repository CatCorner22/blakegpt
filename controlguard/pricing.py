from decimal import Decimal

from .inputs import Fields, fields, finite, items, number

EPSILON = Decimal("1e-9")


def price(data: Fields) -> Fields:
    quantity = number(data.get("quantity"), "quantity")
    invoice_pack = number(data.get("invoice_pack"), "invoice_pack")
    po_pack = number(data.get("po_pack"), "po_pack")
    billed_price = number(data.get("billed_price"), "billed_price")
    list_price = number(data.get("contract_list_price"), "contract_list_price")
    discount = number(data.get("discount"), "discount", 0, 1)
    if discount == 1:
        raise ValueError("discount must be less than 1.")
    invoice_unit = billed_price / max(invoice_pack, EPSILON)
    truth_unit = list_price * (1 - discount) / max(po_pack, EPSILON)
    truth_total = quantity * invoice_pack * truth_unit
    billed_total = quantity * billed_price
    warnings = ["A pack size is below epsilon. Verify the units before relying on this amount."] if (
        min(invoice_pack, po_pack) < EPSILON
    ) else []
    return {"invoice_unit_price": finite(invoice_unit), "truth_unit_price": finite(truth_unit),
            "truth_total": finite(truth_total), "billed_total": finite(billed_total),
            "overcharge": finite(max(Decimal(0), billed_total - truth_total)),
            "flags": ["INV-TRAP-04"] if invoice_pack != po_pack else [], "warnings": warnings}


def skim(data: Fields) -> Fields:
    tolerance = number(data.get("tolerance"), "tolerance", 0, 1)
    invoices = items(data.get("invoices"), "invoices")
    ratios: list[Decimal] = []
    for index, value in enumerate(invoices, start=1):
        invoice = fields(value, f"invoice {index}")
        invoice_unit = number(invoice.get("invoice_unit_price"), "invoice_unit_price")
        po_unit = number(invoice.get("po_unit_price"), "po_unit_price")
        if po_unit == 0:
            raise ValueError(f"Invoice {index} has zero PO unit price; relative variance is undefined.")
        ratios.append((invoice_unit - po_unit) / po_unit)
    count = len(ratios)
    positives = sum(ratio > 0 for ratio in ratios)
    hug = sum(tolerance * Decimal("0.60") <= ratio < tolerance for ratio in ratios)
    flagged = count >= 4 and positives * 10 >= count * 7 and hug * 2 >= count
    return {"sample_size": count, "eligible": count >= 4,
            "positive_skew": positives / count if count else None,
            "ceiling_hug": hug / count if count else None,
            "flagged": flagged, "flags": ["TW-01", "INV-TRAP-05"] if flagged else [],
            "cusum_evaluated": False}
