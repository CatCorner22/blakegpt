import re

from .inputs import Fields, boolean, fields, string

TITLE = re.compile(
    r"^Policy:\s+[A-Za-z0-9 &/]+--[A-Za-z0-9 &/,\-]+\.\s{1,2}[A-Z]{2,6}\s+Policy\s+\d+$"
)
LEXICON = {
    "and/or": None, "pursuant to": "under", "in the event that": "if", "prior to": "before",
    "herein": None, "thereof": None, "wherefore": None, "adequate": None, "appropriate": None,
    "promptly": None, "immediately": None, "reasonable efforts": None, "should": None,
}
HANDBOOK = {
    "HR-GUARD-01": ("front_noncontract_disclaimer", "receipt_and_reading_only"),
    "HR-GUARD-02": ("protects_discussion_of_wages_hours_and_conditions",),
    "HR-GUARD-03": ("allows_direct_agency_reports", "preserves_whistleblower_awards"),
    "HR-GUARD-04": ("preserves_efaa_election", "excepts_speak_out_covered_disputes"),
    "HR-GUARD-05": ("separates_policy_sop_records", "official_plan_controls_summary"),
}
RELATIVE = re.compile(r"\bwithin\s+\d+(?:\.\d+)?\s+(?:hours?|days?)\s+of\b", re.IGNORECASE)
PASSIVE = re.compile(
    r"\b(?:be|is|are|was|were|been|being)\s+(?:\w+ed|made|held|given|sent|paid|kept|done)\b",
    re.IGNORECASE,
)


def policy(data: Fields) -> Fields:
    source = string(data.get("text"), "text")
    kind = string(data.get("kind", "policy"), "kind")
    if kind not in ("policy", "contract"):
        raise ValueError("Use policy or contract.")
    raw_title = data.get("title")
    title_valid: bool | None = None
    if raw_title is not None:
        title = string(raw_title, "title")
        title_valid = TITLE.fullmatch(title) is not None
    flags: list[Fields] = []
    terms = dict(LEXICON)
    if kind == "policy":
        terms.update({"shall": "must, if this is a duty", "reserves the right to": "may",
                      "is authorized to": "may"})
    else:
        terms["shall"] = "Check whether a party has a duty to act."
    for term, suggestion in terms.items():
        for match in re.finditer(r"(?<!\w)" + re.escape(term).replace(r"\ ", r"\s+") + r"(?!\w)",
                                 source, re.IGNORECASE):
            flags.append({"term": match[0], "offset": match.start(), "suggestion": suggestion,
                          "review": kind == "contract" and term == "shall"})
    for pattern, suggestion in ((RELATIVE, "Name the start event and state the deadline."),
                                (PASSIVE, "Check whether the sentence names the actor.")):
        for match in pattern.finditer(source):
            flags.append({"term": match[0], "offset": match.start(), "suggestion": suggestion, "review": True})
    flags.sort(key=lambda flag: int(str(flag["offset"])))
    return {"title_valid": title_valid, "flags": flags,
            "passes_screen": title_valid is not False and not flags, "lexicon_complete": False}


def handbook(data: Fields) -> Fields:
    jurisdiction = string(data.get("jurisdiction"), "jurisdiction").upper()
    if re.fullmatch(r"[A-Z]{2}", jurisdiction) is None:
        raise ValueError("Use a two-letter jurisdiction code.")
    facts = fields(data.get("facts"), "facts")
    rules = HANDBOOK.copy()
    if jurisdiction == "MT":
        rules["HR-GUARD-01-MT"] = ("montana_postprobation_good_cause",)
    else:
        rules["HR-GUARD-01"] += ("at_will_disclaimer",)
    findings: list[Fields] = []
    for rule, keys in rules.items():
        unknown = [key for key in keys if key not in facts]
        failed = [key for key in keys if key in facts and not boolean(facts[key], key)]
        status = "review" if failed else "unknown" if unknown else "asserted"
        findings.append({"id": rule, "status": status, "false": failed, "missing": unknown})
    return {"jurisdiction": jurisdiction, "findings": findings,
            "basis": "User-supplied facts only. This is not a legal determination."}
