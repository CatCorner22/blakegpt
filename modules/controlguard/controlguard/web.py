from html import escape
import http.client
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sqlite3
from urllib.parse import parse_qs

from .app import DISCLAIMER, ENGINES, run_engine
from .inputs import decode, encode
from .ledger import Ledger
from .llm.inference import ask, configured_client

STYLE = """
:root{color-scheme:dark;--ink:#f5f8ff;--dim:#bdc9d8;--edge:#3b506b;--mint:#73eecb}
*{box-sizing:border-box}body{margin:0;background:#0b1728;color:var(--ink);
font:16px/1.55 system-ui,sans-serif}header,main,footer{max-width:960px;margin:auto;padding:1.5rem}
header{padding-top:3rem;padding-bottom:0}.eyebrow{color:var(--mint);font-size:.82rem;
text-transform:uppercase;letter-spacing:.17em}h1{font-size:clamp(2.3rem,8vw,4rem);margin:.15rem 0}
h2{margin:.2rem 0}p{margin:.35rem 0 1rem;color:var(--dim)}.tools{display:grid;
grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr));gap:1rem}
form,section.result{background:#11243b;border:1px solid var(--edge);padding:1.1rem;border-radius:.75rem}
label{display:block;font-weight:600;margin-bottom:.3rem}textarea{width:100%;min-height:9rem;
resize:vertical;background:#0b1728;color:var(--ink);border:1px solid #647d98;border-radius:.4rem;
padding:.6rem;font:13px/1.5 ui-monospace,monospace}button{background:var(--mint);color:#0b1728;
border:0;border-radius:.4rem;padding:.55rem .9rem;font-weight:700;margin-top:.7rem;cursor:pointer}
:focus-visible{outline:3px solid #ffd78f;outline-offset:3px}pre{overflow:auto;white-space:pre-wrap;
overflow-wrap:anywhere}section.result,#ask{margin-bottom:1rem}.error{border-left:4px solid #ffa29e!important}
"""


def page(result: str | None = None, error: bool = False, *, submitted: str | None = None,
         raw: str | None = None, adapter: str | None = None) -> str:
    cards = []
    for key, engine in ENGINES.items():
        hint = (" <small>To sign, set action to append. Add subject, control, signer, actor, "
                "cadence and artifact.</small>") if key == "ledger" else ""
        value = raw if submitted == key and raw is not None else encode(engine.example, pretty=True)
        cards.append(f'<form id="{key}" method="post" action="/{key}#result">'
                     f'<h2>{engine.title}</h2><p>{engine.help}{hint}</p>'
                     f'<label for="input-{key}">{engine.title} · JSON</label>'
                     f'<textarea id="input-{key}" name="input" spellcheck="false" required>'
                     f'{escape(value)}</textarea><button>Run tool</button></form>')
    section = (f'<section class="result{" error" if error else ""}" id="result" '
               f'aria-labelledby="result-heading"><h2 id="result-heading">'
               f'{"Check the input" if error else "Result"}</h2><pre>{escape(result)}</pre></section>'
               if result is not None else "")
    ask_value = raw if submitted == "ask" and raw is not None else ""
    selected = " selected" if adapter == "a2" else ""
    ask_form = ('<form id="ask" method="post" action="/ask#result"><h2>Ask ControlGuard</h2>'
                '<p>Use a local model, if configured. Without one, enter a tool name and JSON, '
                'or start with <code>Convert:</code> for leave. Do not enter personal data.</p>'
                '<label for="adapter">Tool group</label><select id="adapter" name="adapter">'
                '<option value="a1">Policy and leave · A1</option>'
                f'<option value="a2"{selected}>Controls and pricing · A2</option></select>'
                '<label for="ask-input">Request</label><textarea id="ask-input" name="input" required '
                f'placeholder="Convert: Staff earn 1 day/month.">{escape(ask_value)}</textarea>'
                '<button>Run request</button></form>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>ControlGuard</title><style>{STYLE}</style><header>'
            '<span class="eyebrow">Local review tools</span><h1>ControlGuard</h1>'
            '<p>Check business controls, contract prices and policy wording.</p></header>'
            f'<main>{section}{ask_form}<div class="tools">{"".join(cards)}</div></main>'
            f'<footer><p>{DISCLAIMER}</p></footer></html>')


class Handler(BaseHTTPRequestHandler):
    ledger: Ledger
    port: int
    origins: set[str]

    def _send(self, status: HTTPStatus, content: str) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; "
                         "form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _local(self) -> bool:
        return f"http://{self.headers.get('Host')}" in self.origins

    def do_GET(self) -> None:
        if not self._local():
            self.send_error(HTTPStatus.FORBIDDEN)
        elif self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND)
        else:
            self._send(HTTPStatus.OK, page())

    def do_POST(self) -> None:
        if not self._local() or self.headers.get("Origin") not in self.origins:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        engine = self.path.removeprefix("/")
        if engine not in ENGINES and engine != "ask":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        self.connection.settimeout(10)
        raw = adapter = None
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 256_000:
                raise ValueError("Use an input under 256 KB.")
            form = parse_qs(self.rfile.read(size).decode("utf-8"), strict_parsing=True, keep_blank_values=True,
                            max_num_fields=2 if engine == "ask" else 1)
            raw = form.get("input", [""])[0]
            if engine == "ask":
                adapter = form.get("adapter", [""])[0]
                output = ask(raw, adapter, self.ledger, configured_client(adapter))
            else:
                output = run_engine(engine, decode(raw), self.ledger)
            result = encode(output, pretty=True)
        except (OSError, ValueError, RecursionError, sqlite3.Error, http.client.HTTPException) as error:
            self._send(HTTPStatus.BAD_REQUEST, page(str(error), error=True, submitted=engine, raw=raw,
                                                    adapter=adapter))
            return
        self._send(HTTPStatus.OK, page(result, submitted=engine, raw=raw, adapter=adapter))


def serve(port: int, ledger: Ledger) -> None:
    class BoundHandler(Handler):
        pass

    BoundHandler.ledger = ledger
    with ThreadingHTTPServer(("127.0.0.1", port), BoundHandler) as server:
        BoundHandler.port = server.server_port
        BoundHandler.origins = {f"http://{host}:{server.server_port}" for host in ("localhost", "127.0.0.1")}
        print(f"ControlGuard: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return
