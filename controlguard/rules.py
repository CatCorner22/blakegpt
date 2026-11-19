from .inputs import Fields, boolean, fields

CONTRACT = {
    "RULE-01": "unanchored_list_discount",
    "RULE-02": "substitution_raises_price",
    "RULE-03": "uncapped_escalator",
    "RULE-04": "unmapped_discount_category",
    "RULE-05": "markup_includes_unapproved_costs",
    "RULE-06": "retroactive_rebate_clawback_or_cliff",
    "RULE-07": "undisclosed_evergreen_with_rate_increase",
    "RULE-08": "minimum_volume_damages",
    "RULE-09": "unscheduled_surcharge",
    "RULE-10": "gag_clause_confirmed_prohibited",
}
INVOICE = {
    "INV-TRAP-01": "discount_bucket_downgraded",
    "INV-TRAP-02": "unapproved_list_price_increase",
    "INV-TRAP-03": "unapproved_substitution_at_markup",
    "INV-TRAP-06": "surcharge_not_allowed",
    "INV-TRAP-07": "duplicate_or_split_confirmed",
    "INV-TRAP-08": "quantity_exceeds_signed_receipt",
}


def review_rules(data: Fields) -> Fields:
    facts = fields(data.get("facts"), "facts")
    rules = {**CONTRACT, **INVOICE}
    if set(facts).difference(rules.values()):
        raise ValueError("Use only listed contract or invoice fact names.")
    return {"flags": [rule for rule, key in rules.items()
                      if key in facts and boolean(facts[key], key)],
            "not_assessed": [rule for rule, key in rules.items() if key not in facts],
            "fact_keys": rules}
