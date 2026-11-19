from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from controlguard.inputs import Fields, decode, encode, fields, items
from controlguard.ledger import Ledger
from controlguard.llm.dataset import generate
from controlguard.llm.evaluate import load_rows, measure
from controlguard.llm.inference import LocalClient, ask, scrub
from controlguard.llm.model import ModelSpec, REVISIONS, scan_template, verify_tensor
from controlguard.llm.train import completion_for, evaluate_stage, evaluation_sets, has_4bit_weights


def test_held_out_sets_and_eval_scoring(tmp_path: Path) -> None:
    generate(tmp_path, 8, 8)
    for adapter in ("a1", "a2"):
        training = load_rows(tmp_path / f"{adapter}-train.jsonl")
        held_out = load_rows(tmp_path / f"{adapter}-eval.jsonl")
        assert len(training) == len(held_out) == 8
        prompts = [fields(items(row["messages"], "messages")[1])["content"] for row in training]
        assert all(fields(items(row["messages"], "messages")[1])["content"] not in prompts for row in held_out)
        assert all(len(items(row["messages"], "messages")) == 5 for row in held_out)
        perfect = [completion_for(row) for row in held_out]
        assert measure(held_out, perfect) == {
            "examples": 8, "valid_json": 8, "correct_tool": 8, "exact_tool_call": 8,
        }
        perfect[0] = "not JSON"
        perfect[1] = '{"name":"leave","arguments":{"unknown":true}}'
        assert measure(held_out, perfect)["exact_tool_call"] == 6


def test_combined_union_and_partial_family_metrics(tmp_path: Path) -> None:
    generate(tmp_path, 8, 8)
    rows = load_rows(tmp_path / "combined-train.jsonl")
    for index, family in enumerate(("a1", "a2")):
        assert [row["expected"] for row in rows[index::2]] == [
            row["expected"] for row in load_rows(tmp_path / f"{family}-train.jsonl")]
    sets = evaluation_sets(tmp_path, "combined", 4)
    assert all(len(items(row["tools"], "tools")) == 6 for row in rows + sets["a1"] + sets["a2"])
    metrics: Fields = {}
    perfect = [[completion_for(row) for row in family_rows] for family_rows in sets.values()]
    with patch("controlguard.llm.train.predictions", side_effect=perfect):
        evaluate_stage(None, None, None, sets, tmp_path, "before", metrics)
    with patch("controlguard.llm.train.predictions", side_effect=[perfect[0], RuntimeError("failed")]):
        with pytest.raises(RuntimeError, match="failed"):
            evaluate_stage(None, None, None, sets, tmp_path, "after", metrics)
    saved = decode((tmp_path / "metrics.json").read_text())
    before, after = fields(saved["before"]), fields(saved["after"])
    assert before["exact_tool_call"] == 8
    assert set(fields(before["per_family"])) == {"a1", "a2"}
    assert set(fields(after["per_family"])) == {"a1"}


def test_model_pins_and_header(tmp_path: Path) -> None:
    for repo, revision in REVISIONS.items():
        ModelSpec(repo, revision).validate()
    with pytest.raises(ValueError, match="blocked"):
        ModelSpec("Qwen/Qwen2.5-72B", "a" * 40).validate()
    with pytest.raises(ValueError, match="pinned"):
        ModelSpec("Qwen/Qwen3-8B", "main").validate()
    with pytest.raises(ValueError, match="blocked"):
        scan_template("{{ x.__globals__ }}")
    with pytest.raises(ValueError, match="reviewed"):
        scan_template("{{ messages }}")
    file = tmp_path / "test.safetensors"
    good = b'{"X":{"data_offsets":[0,3]}}'
    file.write_bytes(len(good).to_bytes(8, "little") + good + b"ABC")
    verify_tensor(file)
    bad = b'{"X":{"data_offsets":[0,2]},"Y":{"data_offsets":[1,3]}}'
    file.write_bytes(len(bad).to_bytes(8, "little") + bad + b"ABC")
    with pytest.raises(ValueError, match="overlap"):
        verify_tensor(file)


def test_4bit_check_requires_materialized_quantized_weights() -> None:
    class Linear4bit:
        def __init__(self, quant_state: object) -> None:
            self.weight = SimpleNamespace(quant_state=quant_state)

    assert has_4bit_weights(SimpleNamespace(modules=lambda: [Linear4bit(object())]), Linear4bit)
    assert not has_4bit_weights(SimpleNamespace(modules=lambda: [Linear4bit(None)]), Linear4bit)
    dense = SimpleNamespace(is_loaded_in_4bit=True, modules=lambda: [object()])
    assert not has_4bit_weights(dense, Linear4bit)


def test_fallback_and_redaction(tmp_path: Path) -> None:
    assert scrub("SSN: 123-45-6789; 14 Main Street; test@example.com; routing: 123456789") == (
        "[REDACTED]; [REDACTED]; [REDACTED]; [REDACTED]")
    ledger = Ledger(tmp_path / "unused.sqlite3")
    result = ask(" Convert: Staff earn 1 day/month. ", "a1", ledger)
    assert result["mode"] == "rules" and "8.0 hours" in encode(result)
    assert ask("What is my risk?", "a2", ledger)["status"] == "needs_input"
    assert ask('policy {"text":"Staff must file it."}', "a1", ledger)["status"] == "complete"
    with pytest.raises(ValueError, match="local"):
        LocalClient("http://127.0.0.1.example.com/v1", "qwen")


def test_chat_http_loop_validates_and_redacts(tmp_path: Path) -> None:
    requests: list[Fields] = []
    replies = [
        {"tool_calls": [{"id": "external", "type": "function", "function": {
            "name": "leave", "arguments": encode({"text": "Staff earn 1 day/month.", "shift_hours": 6}),
        }}]},
        {"content": '{"status":"complete"}'},
        {"tool_calls": [{"id": "bad", "type": "function", "function": {
            "name": "ledger", "arguments": '{"action":"append"}',
        }}]},
    ]

    class ModelStub(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            assert self.path == "/v1/chat/completions"
            requests.append(decode(self.rfile.read(int(self.headers["Content-Length"])).decode()))
            raw = encode({"choices": [{"message": replies.pop(0)}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    ledger = Ledger(tmp_path / "unused.sqlite3")
    with ThreadingHTTPServer(("127.0.0.1", 0), ModelStub) as server:
        worker = Thread(target=server.serve_forever)
        worker.start()
        try:
            client = LocalClient(f"http://127.0.0.1:{server.server_port}/v1", "qwen")
            result = ask("Convert leave. SSN: 123-45-6789", "a1", ledger, client)
            assert result["status"] == "complete" and "6.0 hours" in encode(result)
            assert "123-45-6789" not in encode(requests[0])
            assert requests[0]["tool_choice"] == "auto"
            assert fields(requests[1]["response_format"])["type"] == "json_schema"
            assert "6.0 hours" in encode(requests[1])
            with pytest.raises(ValueError, match="outside this adapter"):
                ask("Append a sign-off.", "a1", ledger, client)
            assert not ledger.path.exists()
        finally:
            server.shutdown()
            worker.join()
