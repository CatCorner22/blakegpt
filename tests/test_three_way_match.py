from decimal import Decimal

from tools.three_way_match import match


def po(qty: str = "2", price: str = "10", line: str = "1") -> dict[str, str]:
    return {"po": "PO-1", "line": line, "item": "Item", "qty": qty, "unit_price": price}


def receipt(qty: str = "2", line: str = "1") -> dict[str, str]:
    return {"po": "PO-1", "line": line, "qty_received": qty}


def invoice(
    number: str = "INV-1",
    *,
    qty: str = "2",
    price: str = "10",
    po_number: str = "PO-1",
    line: str = "1",
    vendor: str = "Vendor A",
    date: str = "",
) -> dict[str, str]:
    return {
        "invoice": number,
        "po": po_number,
        "line": line,
        "qty": qty,
        "unit_price": price,
        "vendor": vendor,
        "date": date,
    }


def test_match_status() -> None:
    results = match([po()], [receipt()], [invoice()])
    assert results[0].status == "MATCH"


def test_no_po_status() -> None:
    results = match([], [receipt()], [invoice()])
    assert results[0].status == "NO-PO"


def test_no_receipt_status() -> None:
    results = match([po()], [], [invoice()])
    assert results[0].status == "NO-RECEIPT"


def test_quantity_over_received_status() -> None:
    results = match([po()], [receipt("1")], [invoice(qty="2")])
    assert results[0].status == "QTY-OVER-RECEIVED"


def test_price_variance_and_tolerance() -> None:
    results = match([po()], [receipt()], [invoice(price="11")])
    assert results[0].status == "PRICE-VARIANCE"
    tolerated = match([po()], [receipt()], [invoice(price="11")], Decimal("10"))
    assert tolerated[0].status == "MATCH"


def test_invoice_split_flag() -> None:
    invoices = [
        invoice("INV-201", qty="6", price="10", date="2026-06-01"),
        invoice("INV-202", qty="6", price="10", date="2026-06-02"),
    ]
    results = match([po()], [receipt()], invoices, approval_threshold="100")
    assert all("INVOICE-SPLIT" in result.flags for result in results)


def test_sequential_invoice_flag() -> None:
    invoices = [
        invoice(f"INV-{number}", date=f"2026-06-0{index}")
        for index, number in enumerate((301, 302, 303), 1)
    ]
    results = match([po()], [receipt()], invoices)
    assert all("SEQUENTIAL-INVOICE" in result.flags for result in results)
