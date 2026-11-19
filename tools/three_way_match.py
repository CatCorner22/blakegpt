from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass
class MatchRow:
    invoice: str
    po: str
    line: str
    status: str
    flags: list[str] = field(default_factory=list)


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"invalid numeric value: {value!r}") from exc
    if not result.is_finite():
        raise ValueError("numeric values must be finite")
    return result


def _date(value: str) -> datetime | None:
    clean = value.strip()
    if not clean:
        return None
    try:
        parsed = datetime.fromisoformat(clean.replace("Z", "+00:00"))
    except ValueError:
        return datetime.combine(date.fromisoformat(clean), time.min)
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def match(
    po_rows: list[dict[str, str]],
    receipt_rows: list[dict[str, str]],
    invoice_rows: list[dict[str, str]],
    price_tolerance_pct: Decimal | str | float = Decimal("0"),
    approval_threshold: Decimal | str | float = Decimal("5000"),
    window_hours: int = 72,
) -> list[MatchRow]:
    tolerance = _decimal(str(price_tolerance_pct))
    approval = _decimal(str(approval_threshold))
    if tolerance < 0 or approval < 0:
        raise ValueError("price tolerance and approval threshold must not be negative")
    purchase_orders = {
        (row["po"], row["line"]): {
            "qty": _decimal(row["qty"]),
            "unit_price": _decimal(row["unit_price"]),
        }
        for row in po_rows
    }
    received: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for row in receipt_rows:
        received[(row["po"], row["line"])] += _decimal(row["qty_received"])

    parsed_invoices: list[dict[str, object]] = []
    totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    invoice_dates: dict[tuple[str, str], datetime | None] = {}
    for row in invoice_rows:
        qty = _decimal(row["qty"])
        price = _decimal(row["unit_price"])
        amount = qty * price
        invoice = row["invoice"]
        vendor = row.get("vendor", "").casefold()
        invoice_key = (vendor, invoice)
        invoice_date = _date(row.get("date", ""))
        parsed = {
            **row,
            "qty_decimal": qty,
            "price_decimal": price,
            "amount": amount,
            "date_parsed": invoice_date,
        }
        parsed_invoices.append(parsed)
        totals[invoice_key] += amount
        if invoice_key not in invoice_dates or invoice_dates[invoice_key] is None:
            invoice_dates[invoice_key] = invoice_date

    results: list[MatchRow] = []
    invoice_indexes: dict[tuple[str, str], list[int]] = defaultdict(list)
    invoiced_quantities: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for index, row in enumerate(parsed_invoices):
        key = (str(row["po"]), str(row["line"]))
        invoiced_quantities[key] += row["qty_decimal"]
        po = purchase_orders.get(key)
        if po is None:
            status = "NO-PO"
        elif key not in received:
            status = "NO-RECEIPT"
        elif invoiced_quantities[key] > received[key]:
            status = "QTY-OVER-RECEIVED"
        elif invoiced_quantities[key] > po["qty"]:
            status = "QTY-OVER-ORDERED"
        else:
            po_price = po["unit_price"]
            invoice_price = row["price_decimal"]
            if po_price == 0:
                variance = Decimal("0") if invoice_price == 0 else Decimal("Infinity")
            else:
                variance = abs(invoice_price - po_price) / abs(po_price) * Decimal("100")
            status = "PRICE-VARIANCE" if variance > tolerance else "MATCH"
        result = MatchRow(str(row["invoice"]), key[0], key[1], status)
        invoice_key = (str(row.get("vendor", "")).casefold(), str(row["invoice"]))
        invoice_indexes[invoice_key].append(index)
        results.append(result)

    by_vendor: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for invoice_key in totals:
        by_vendor[invoice_key[0]].add(invoice_key)
    window_seconds = window_hours * 60 * 60
    for vendor_invoices in by_vendor.values():
        candidates = [
            invoice
            for invoice in vendor_invoices
            if totals[invoice] < approval and invoice_dates[invoice] is not None
        ]
        candidates.sort(key=lambda invoice: invoice_dates[invoice])
        for start in range(len(candidates)):
            total = Decimal("0")
            first_date = invoice_dates[candidates[start]]
            assert first_date is not None
            for end in range(start, len(candidates)):
                invoice = candidates[end]
                current_date = invoice_dates[invoice]
                assert current_date is not None
                if (current_date - first_date).total_seconds() > window_seconds:
                    break
                total += totals[invoice]
                if end > start and total >= approval:
                    for affected in candidates[start : end + 1]:
                        for result_index in invoice_indexes[affected]:
                            if "INVOICE-SPLIT" not in results[result_index].flags:
                                results[result_index].flags.append("INVOICE-SPLIT")

    for vendor_invoices in by_vendor.values():
        numbered: list[tuple[int, tuple[str, str]]] = []
        for invoice_key in vendor_invoices:
            found = re.search(r"(\d+)$", invoice_key[1])
            if found:
                numbered.append((int(found.group(1)), invoice_key))
        numbered.sort()
        run: list[str] = []
        previous: int | None = None
        for number, invoice in numbered:
            if previous is None or number == previous + 1:
                run.append(invoice)
            else:
                if len(run) >= 3:
                    for member in run:
                        for result_index in invoice_indexes[member]:
                            results[result_index].flags.append("SEQUENTIAL-INVOICE")
                run = [invoice]
            previous = number
        if len(run) >= 3:
            for member in run:
                for result_index in invoice_indexes[member]:
                    results[result_index].flags.append("SEQUENTIAL-INVOICE")

    for result in results:
        result.flags = sorted(set(result.flags))
    return results


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def main() -> int:
    parser = argparse.ArgumentParser(description="Match purchase orders, receipts, and invoices.")
    parser.add_argument("po", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("invoice", type=Path)
    parser.add_argument("--price-tolerance-pct", type=Decimal, default=Decimal("0"))
    parser.add_argument("--approval-threshold", type=Decimal, default=Decimal("5000"))
    parser.add_argument("--window-hours", type=int, default=72)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    results = match(
        _read_csv(args.po),
        _read_csv(args.receipt),
        _read_csv(args.invoice),
        args.price_tolerance_pct,
        args.approval_threshold,
        args.window_hours,
    )
    if args.json:
        print(json.dumps([asdict(row) for row in results], indent=2))
    elif results:
        for row in results:
            flags = f" ({', '.join(row.flags)})" if row.flags else ""
            print(f"{row.invoice} PO {row.po} line {row.line}: {row.status}{flags}")
    else:
        print("No invoice lines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
