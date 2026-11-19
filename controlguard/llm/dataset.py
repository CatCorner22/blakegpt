import argparse
from dataclasses import dataclass
from pathlib import Path
import random

from controlguard.app import run_engine
from controlguard.inputs import Fields, encode
from controlguard.ledger import Ledger
from controlguard.risk import GATES

from .tools import ADAPTERS, FAMILIES, SCHEMAS, SYSTEM, tools_for, validate


@dataclass(frozen=True)
class Example:
    name: str
    prompt: str
    arguments: Fields


def exercise(adapter: str, split: str, index: int) -> Example:
    train = split == "train"
    rand = random.Random((0 if train else 100_003) + index)
    if adapter == "a1":
        if index % 2:
            shift = rand.choice((6, 8, 10, 12))
            count = rand.randrange(1, 6) if train else rand.randrange(7, 12)
            source = (f"Staff earn {count} days/month." if train else f"Staff may carry over {count} days/year.")
            prompt = (f"Use a {shift}-hour shift. Convert this leave text: {source}" if train
                      else f"Translate this leave clause to hours with {shift} hours per shift: {source}")
            return Example("leave", prompt, {"text": source, "shift_hours": shift})
        department, topic, code, role, duty = rand.choice(
            (("Finance", "Receipts", "FIN", "bookkeeper", "file the receipts"),
             ("Human Resources", "Leave", "HR", "manager", "record each request"),
             ("Operations", "Training", "OPS", "supervisor", "log each session")) if train else
            (("Information Technology", "Access", "IT", "administrator", "revoke access"),
             ("Human Resources", "Benefits", "HR", "coordinator", "record each enrollment"))
        )
        count = index + (1 if train else 700)
        title = f"Policy: {department}--{topic}.  {code} Policy {count}"
        source = f"The {role} must {duty}."
        prompt = (f'Write and screen a policy titled "{title}". Require the {role} to {duty}.' if train
                  else f'Use "{title}" as the heading. Check this draft: {source}')
        return Example("policy", prompt, {"text": source, "title": title})
    match index % 4:
        case 0:
            quantity, inv, po = rand.randrange(2, 15), rand.choice((4, 6)), rand.choice((8, 12))
            billed, listed = rand.randrange(20, 80), rand.randrange(25, 100)
            discount = rand.choice((.05, .1, .2, .25))
            prompt = (f"Audit {quantity} billed packs of {inv}, at {billed} each. The PO pack is {po}; "
                      f"contract list price {listed} with discount {discount:.0%}." if train else
                      f"My invoice shows {quantity} packs at {billed}, each containing {inv}. The contract lists "
                      f"{listed}, discount {discount:.0%}, PO pack size {po}. Check the unit and total price.")
            return Example("price", prompt, {"quantity": quantity, "invoice_pack": inv, "po_pack": po,
                           "billed_price": billed, "contract_list_price": listed, "discount": discount})
        case 1:
            role = f"role-{index + (0 if train else 800)}"
            impact, exploitability = rand.randrange(4, 11), rand.randrange(4, 11)
            a, b = ("authorization", "custody") if train else ("recordkeeping", "reconciliation")
            asset = "Payables" if train else "Payroll"
            return Example("sod", f"Check {role} for duty conflicts in {asset}. They hold {a} and {b}. "
                           f"Impact {impact}; exploitability {exploitability}.",
                           {"subject": role, "asset_class": asset, "vertices": [a, b], "impact": impact,
                            "exploitability": exploitability})
        case 2:
            gates = dict.fromkeys(GATES, False)
            active = rand.choice((*GATES, "")) if train else "active_incident"
            if active:
                gates[active] = True
            factors = {"impact": rand.randrange(1, 6), "likelihood": rand.randrange(1, 6),
                       "legal": rand.choice((0, 2, 4, 6)), "detection": rand.choice((0, 2, 3)),
                       "recoverability": rand.choice((0, 2, 3)), "aggregation": rand.choice((0, 2))}
            gate_text = ", ".join(f"{k.replace('_', ' ')} is {str(v).lower()}" for k, v in gates.items())
            details = ", ".join(f"{k} {v}" for k, v in factors.items())
            return Example("triage", f"Triage one finding: {gate_text}. Factors: {details}.",
                           {"gates": gates, **factors})
        case _:
            base = rand.choice((100, 200)) if train else 300
            billed_values = [base + rand.randrange(-3, 6) for _ in range(4)]
            prompt = (f"Check one vendor for PO skimming. Tolerance 5%. PO price {base} each time; "
                      f"billed prices {', '.join(map(str, billed_values))}.")
            return Example("skim", prompt, {"tolerance": .05, "invoices": [
                {"invoice_unit_price": value, "po_unit_price": base} for value in billed_values
            ]})


def record(example: Example, adapter: str) -> Fields:
    validate(example.arguments, SCHEMAS[example.name])
    result = run_engine(example.name, example.arguments, Ledger(Path("/dev/null/controlguard.sqlite3")))
    if example.name == "policy" and result["passes_screen"] is not True:
        raise ValueError("A policy target failed lexical screening.")
    function = {"name": example.name, "arguments": encode(example.arguments)}
    return {"tools": tools_for(ADAPTERS[adapter]), "messages": [
        {"role": "system", "content": SYSTEM}, {"role": "user", "content": example.prompt},
        {"role": "assistant", "content": None, "tool_calls": [
            {"type": "function", "id": "call_1", "function": function},
        ]},
        {"role": "tool", "tool_call_id": "call_1", "content": encode(result)},
        {"role": "assistant", "content": encode({"status": "complete"})},
    ], "expected": {"name": example.name, "arguments": example.arguments}}


def with_combined_tools(row: Fields) -> Fields:
    return {**row, "tools": tools_for(ADAPTERS["combined"])}


def precog_example(index: int) -> Example:
    rand = random.Random(200_003 + index)
    start = f"{rand.randrange(2024, 2035)}-{rand.randrange(1, 13):02d}-{rand.randrange(1, 32):02d}"
    notice = rand.choice((30, 45, 60, 75, 90))
    if index % 2:
        term = rand.choice((90, 180, 365, 730))
        return Example("cliff", f"A contract starts on {start} and runs for {term} days. "
                       f"We need {notice} days' notice. Find the deadline.",
                       {"start": start, "notice_days": notice, "term_days": term})
    term = rand.randrange(1, 49)
    return Example("cliff", f"A {term}-month license starts on {start}. The notice period is {notice} days.",
                   {"start": start, "notice_days": notice, "term_months": term})


def generate(output: Path, train_count: int, eval_count: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for adapter in FAMILIES:
        for split, count in (("train", train_count), ("eval", eval_count)):
            with (output / f"{adapter}-{split}.jsonl").open("w", encoding="utf-8") as stream:
                for index in range(count):
                    print(encode(record(exercise(adapter, split, index), adapter)), file=stream)
    for split, count in (("train", train_count), ("eval", eval_count)):
        pairs = ((family, index) for index in range(count) for family in FAMILIES) if split == "train" else (
            (family, index) for family in FAMILIES for index in range(count))
        with (output / f"combined-{split}.jsonl").open("w", encoding="utf-8") as stream:
            for family, index in pairs:
                row = record(exercise(family, split, index), family)
                print(encode(with_combined_tools(row)), file=stream)
                if split == "train" and family == "a2" and index % 3 == 0:
                    print(encode(record(precog_example(index), "combined")), file=stream)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic ControlGuard adapter examples.")
    parser.add_argument("--output", type=Path, default=Path("llm-output/data"))
    parser.add_argument("--train-count", type=int, default=160)
    parser.add_argument("--eval-count", type=int, default=32)
    args = parser.parse_args()
    if not 1 <= args.train_count <= 100_000 or not 1 <= args.eval_count <= 10_000:
        parser.error("Use a positive example count within the supported range.")
    generate(args.output, args.train_count, args.eval_count)
    print(f"Wrote A1 and A2: {args.train_count} training and {args.eval_count} held-out examples each.")


if __name__ == "__main__":
    main()
