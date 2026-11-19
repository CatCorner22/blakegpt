from io import StringIO
import sys

from evals.blakegpt_eval_v2 import CASES, score_case
from tools.draft_guard import guard, main, route


def test_contract_fixes_number_doublet_and_party_modals() -> None:
    text = (
        "The Vendor must provide the Practice with thirty (30) days' written "
        "notice before ending this Agreement."
    )

    result = guard(text, "contract")

    assert result.text.startswith(
        "The Vendor shall provide the Practice with 30 days' written notice "
        "before ending this Agreement."
    )
    assert result.fixed == ["must -> shall", "thirty (30) -> 30"]
    assert not {finding.rule for finding in result.flags} & {"R-DIGITS", "R-MODAL"}
    assert "Drafting check (tools/draft_guard.py): fixed 2 item(s):" in result.text


def test_contract_fixes_doublet_when_modal_is_already_shall() -> None:
    result = guard(
        "The Vendor shall give the Practice thirty (30) days' written notice",
        "contract",
    )

    assert result.text.startswith(
        "The Vendor shall give the Practice 30 days' written notice"
    )
    assert result.fixed == ["thirty (30) -> 30"]


def test_number_doublet_replaces_the_complete_number_word_phrase() -> None:
    hundred = guard("one hundred (100) days", "contract")
    hyphenated = guard("twenty-one (21) days", "contract")

    assert hundred.text.startswith("100 days")
    assert hundred.fixed == ["one hundred (100) -> 100"]
    assert hyphenated.text.startswith("21 days")
    assert hyphenated.fixed == ["twenty-one (21) -> 21"]


def test_contract_fixes_will_for_an_explicitly_defined_party() -> None:
    result = guard("Vendor will provide written notice.", "contract", ["Vendor"])

    assert result.fixed == ["will -> shall"]
    assert result.text.startswith("Vendor shall provide written notice.")


def test_contract_modal_fixes_only_known_parties_and_not_before_be() -> None:
    notice = "The Notice must be in writing to take effect."
    insured = "The Vendor must be insured."

    notice_result = guard(notice, "contract")
    insured_result = guard(insured, "contract")

    assert notice_result.text == notice
    assert notice_result.fixed == []
    assert insured_result.text.startswith(insured)
    assert "shall be insured" not in insured_result.text
    assert "must -> shall" not in insured_result.fixed


def test_cited_quotes_are_preserved_but_uncited_drafts_are_fixed() -> None:
    cited = '"The Vendor must provide thirty (30) days." (29 CFR 1910.1030(f)(2))'
    uncited = "“The Vendor must provide thirty (30) days.”"

    cited_result = guard(cited, "contract")
    uncited_result = guard(uncited, "contract")

    assert cited_result.text.startswith(cited)
    assert cited_result.fixed == []
    assert "“The Vendor shall provide 30 days.”" in uncited_result.text
    assert uncited_result.fixed == ["must -> shall", "thirty (30) -> 30"]


def test_guard_does_not_change_quoted_lines_or_backtick_text() -> None:
    quoted = "> within thirty (30) days"
    quoted_result = guard(quoted, "contract")
    code = "Use `thirty (30)` exactly."
    code_result = guard(code, "contract")

    assert quoted_result.text == quoted
    assert quoted_result.fixed == []
    assert "`thirty (30)`" in code_result.text
    assert code_result.fixed == []


def test_contract_does_not_change_nonparty_modal() -> None:
    text = "This sentence must use shall."
    lowercase_subject = "the Vendor must provide written notice."

    result = guard(text, "contract")
    lowercase_result = guard(lowercase_subject, "contract")

    assert result.text == text
    assert result.fixed == []
    assert not result.flags
    assert lowercase_result.text == lowercase_subject
    assert lowercase_result.fixed == []


def test_one_way_modal_stays_a_flag_and_adds_footer() -> None:
    text = "Staff should wipe each chair."

    result = guard(text, "one-way")

    assert result.text.startswith(text)
    assert result.fixed == []
    assert [finding.rule for finding in result.flags] == ["R-MODAL"]
    assert (
        "Drafting check (tools/draft_guard.py): fixed 0 item(s): none; "
        "1 item(s) to review: R-MODAL line 1 'Staff should wipe each chair.'"
    ) in result.text


def test_clean_draft_has_no_footer() -> None:
    text = "The Vendor shall give the Practice 30 days' written notice."

    result = guard(text, "contract")

    assert result.text == text
    assert result.fixed == []
    assert result.flags == []


def test_route_uses_drafting_verb_and_document_type() -> None:
    cases = {case[0]: case[1] for case in CASES}

    assert route(cases["mscd-digits"]) == "contract"
    assert route(cases["oneway-sop"]) == "one-way"
    assert route("Rewrite our vendor agreements and policies.") == "contract"
    assert route("How often must we review our exposure control plan?") is None


def test_stored_32b_mscd_reply_passes_shared_scoring_after_guard() -> None:
    reply = '''**Contract Sentence:**

"The Vendor shall give the Practice thirty (30) days' written notice before ending this Agreement."'''
    case = next(case for case in CASES if case[0] == "mscd-digits")
    guarded = guard(reply, "contract").text

    scored = score_case(case, guarded, 0.0, [])

    assert scored["pass"]
    assert scored["need"] == {r"\b30\b": True, r"\bshall\b": True}
    assert scored["forbidden"] == []


def test_cli_reads_stdin_and_prints_guarded_text(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["draft_guard", "-", "--mode", "contract"])
    monkeypatch.setattr(
        sys,
        "stdin",
        StringIO("The Vendor must give the Practice thirty (30) days' written notice."),
    )

    assert main() == 0

    output = capsys.readouterr().out
    assert output.startswith(
        "The Vendor shall give the Practice 30 days' written notice."
    )
    assert "Drafting check (tools/draft_guard.py): fixed 2 item(s):" in output
