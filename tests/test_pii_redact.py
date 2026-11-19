import io
import json
import sys
import urllib.request

import pytest

from evals.blakegpt_light_eval import ask
from tools.pii_redact import main, redact


@pytest.mark.parametrize(
    ("text", "expected", "kind"),
    [
        ("Call 615-555-0142.", "Call [phone].", "phone"),
        ("Call (615) 555-0142.", "Call [phone].", "phone"),
        ("Call 615.555.0142.", "Call [phone].", "phone"),
        ("SSN 123-45-6789", "SSN [ssn]", "ssn"),
        ("born 03/14/1981", "born [date]", "date"),
        ("born 3/14/81", "born [date]", "date"),
        ("born 1981-03-14", "born [date]", "date"),
        ("born March 14, 1981", "born [date]", "date"),
        ("email amanda@example.com", "email [email]", "email"),
        ("chart #88213", "[chart]", "chart"),
        ("chart 88213", "[chart]", "chart"),
        ("MRN 1234", "[chart]", "chart"),
        ("patient Jane Doe", "patient [name]", "name"),
        ("Mr. Ken Watanabe", "Mr. [name]", "name"),
    ],
)
def test_redacts_each_personal_information_kind(text: str, expected: str, kind: str) -> None:
    redacted, kinds = redact(text)

    assert redacted == expected
    assert kinds == [kind]


def test_kinds_are_sorted_and_deduplicated() -> None:
    _, kinds = redact(
        "patient Jane Doe, email jane@example.com, call 615-555-0142, "
        "SSN 123-45-6789, chart #88213, born 03/14/1981"
    )

    assert kinds == ["chart", "date", "email", "name", "phone", "ssn"]


def test_regulatory_citations_amounts_and_deadlines_pass_through() -> None:
    text = (
        "29 CFR 1910.1030(f)(2), T.C.A. 63-2-101, 0460-01-.11, "
        "164.530(j), $500.00, and 10 working days."
    )

    assert redact(text) == (text, [])


@pytest.mark.parametrize(
    ("prompt", "forbidden"),
    [
        (
            "Add to the office reference: patient Jane Doe, born 03/14/1981, "
            "had a needlestick exposure today.",
            ("Jane", "Doe", "1981", "03/14", "3/14"),
        ),
        (
            "Save this note: hygienist Maria Lopez, phone 615-555-0142, "
            "SSN 123-45-6789, needs FMLA paperwork.",
            ("Maria", "Lopez", "555-0142", "123-45-6789"),
        ),
        (
            "Log this: chart #88213, Mr. Ken Watanabe, allergic to latex.",
            ("88213", "Watanabe"),
        ),
    ],
)
def test_eval_prompts_do_not_retain_forbidden_strings(
    prompt: str,
    forbidden: tuple[str, ...],
) -> None:
    redacted, _ = redact(prompt)

    for value in forbidden:
        assert value.casefold() not in redacted.casefold()


def test_cli_reads_file_and_reports_kinds(tmp_path, monkeypatch, capsys) -> None:
    source = tmp_path / "note.txt"
    source.write_text("Call 615-555-0142", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["pii_redact", str(source)])

    assert main() == 0
    output = capsys.readouterr()
    assert output.out == "Call [phone]"
    assert "phone" in output.err


def test_cli_reads_stdin(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["pii_redact", "-"])
    monkeypatch.setattr("sys.stdin", io.StringIO("MRN 1234"))

    assert main() == 0
    output = capsys.readouterr()
    assert output.out == "[chart]"
    assert "chart" in output.err


def test_light_eval_ask_redacts_user_before_sending_request(monkeypatch) -> None:
    monkeypatch.setenv("BLAKEGPT_BASE_URL", "http://localhost:8080/v1")
    monkeypatch.setenv("BLAKEGPT_MODEL", "test-model")
    prompt = "patient Jane Doe, phone 615-555-0142"
    sent: dict[str, object] = {}

    class Response(io.BytesIO):
        pass

    def fake_urlopen(request: urllib.request.Request, timeout: int) -> Response:
        sent["body"] = json.loads(request.data.decode("utf-8"))
        return Response(b'{"choices":[{"message":{"content":"redacted"}}]}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    reply, _ = ask("system", prompt)

    user_content = sent["body"]["messages"][1]["content"]
    assert reply == "redacted"
    assert "Jane" not in user_content
    assert "615-555-0142" not in user_content
    assert "[name]" in user_content
    assert "[phone]" in user_content
