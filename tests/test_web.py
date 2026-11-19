from html import escape
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

import pytest

from controlguard.ledger import Ledger
from controlguard.web import Handler


def test_forms_keep_submitted_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONTROLGUARD_MODEL_URL", raising=False)
    class TestHandler(Handler):
        ledger = Ledger(tmp_path / "ledger.sqlite3")

    with ThreadingHTTPServer(("127.0.0.1", 0), TestHandler) as server:
        origin = f"http://127.0.0.1:{server.server_port}"
        TestHandler.origins = {origin}
        worker = Thread(target=server.serve_forever)
        worker.start()
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)

        def post(tool: str, **form: str) -> tuple[int, str]:
            connection.request("POST", f"/{tool}", urlencode(form), {
                "Content-Type": "application/x-www-form-urlencoded", "Origin": origin,
            })
            response = connection.getresponse()
            return response.status, response.read().decode()

        try:
            invoice = '{"quantity": -1, "invoice_pack": 42, "note": "</textarea>"}'
            status, body = post("price", input=invoice)
            assert status == 400
            assert f'required>{escape(invoice)}</textarea>' in body
            status, body = post("price", input="")
            assert status == 400
            assert 'id="input-price" name="input" spellcheck="false" required></textarea>' in body

            request = "Convert: Staff earn 1–2 days/month."
            status, body = post("ask", input=request, adapter="a1")
            assert status == 200
            assert r"8.0\u201316.0 hours per calendar month" in body
            assert f">{escape(request)}</textarea>" in body

            request = "price {"
            status, body = post("ask", input=request, adapter="a2")
            assert status == 400
            assert f">{request}</textarea>" in body
            assert '<option value="a2" selected>' in body
        finally:
            connection.close()
            server.shutdown()
            worker.join()
