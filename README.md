# ControlGuard

Run local checks for business controls, invoice prices, notice deadlines and policy wording. Python calculates every reported result. The optional Ask panel uses a local model to extract facts or propose policy wording, then runs the same checks. It does not use Gemini or a cloud API.

Use these findings to guide review. They do not provide legal advice, an audit opinion or a CPA attestation. See [REVIEW.md](REVIEW.md) for source checks and production blockers.

## Run the tools

Use Python 3.11 or later. The CLI and web app have no third-party runtime dependencies.

```sh
python -m controlguard web --port 8765
printf '%s\n' '{"start":"2026-01-31","term_months":12,"notice_days":60}' | python -m controlguard run cliff
python -m controlguard run price invoice.json
```

Open <http://127.0.0.1:8765>. Each form includes an example JSON object. The CLI accepts a JSON file or reads from standard input. It prints a JSON result, or an error to standard error and exits with status 2. Set `CONTROLGUARD_LEDGER` or pass `--ledger PATH` **before** the command to select a SQLite file. The default is `controlguard.sqlite3` in the current directory.

| Tool | What it checks |
|---|---|
| `triage` | Four reviewer-supplied gates, then the six-term score. Local tier thresholds: 24, 16 and 9. A gate overrides scoring. |
| `sod` | One subject and asset class per request. Two or more distinct duties trigger scoring. Priority thresholds: 60, 35 and 15. |
| `ledger` | Append a named sign-off or verify the full SHA-256 chain. The tool does not authenticate signers or store the evidence itself. |
| `price` | Compare per-item and extended prices. Enter quantity in billed packs and prices per pack. The tool flags mismatched pack sizes and warns about packs below epsilon. |
| `skim` | Use one normalized price comparison per invoice for one vendor. The detector needs at least four invoices. It does not evaluate unspecified CUSUM logic. |
| `cliff` | Supply `term_days` or `term_months` and `notice_days`. The tool clamps numeric start components and clamps month-based terms to the destination month's last day. It returns dates, not messages or renewals. |
| `leave` | Convert numeric day and half-day units in shift-based leave text. The tool uses eight hours per shift by default and flags unresolved day units. It compares an optional usage increment with the selected minimum. Do not submit calendar, banking or legal deadlines for shift conversion. |
| `policy` | Check a supplied title and flag listed lexical patterns and possible passive voice. It does not infer a contract party's duty or rewrite legal terms. |
| `handbook` | Check supplied facts against five guardrails and a Montana branch. `asserted` means the caller affirmed the listed facts, not that the tool established compliance. |
| `rules` | Check structured contract and invoice assertions. The tool does not extract facts from contracts, redline clauses, or send demands. |
| `catalog` | Browse C, DEF, O, TW, CON, FT, RULE and INV-TRAP reference data. FT entries identify missing rules. The review lists the citations it checks. |

To request a triage credit or SoD factor below 1.00, set all three `compensating_has_*` flags (`actor`, `cadence`, `artifact`) to true. Enter the `subject` and `control` that the ledger sign-off records. Use a control key unique to the finding and asset. At 336 elapsed hours, the tool removes the reduction and recomputes the score. A local operator can replace the database or remove its tail; preserve and independently anchor a trusted ledger head before relying on the chain.

```sh
printf '%s\n' '{"action":"append","subject":"role-1","control":"payables-C4-1","signer":"Owner","actor":"Independent reviewer","cadence":"Weekly","artifact":"Exception log reference 001"}' |
  python -m controlguard run ledger
printf '%s\n' '{"action":"verify"}' | python -m controlguard run ledger
```

## Use a local model

With no model configuration, **Ask ControlGuard** uses a rule-based router. Select A1 and enter `Convert: Staff earn 1 day/month.`, or enter a tool name, a space and a JSON object. A1 handles policy and leave. A2 handles triage, conflicts, invoice pricing and PO tolerance.

To connect a local server, set the OpenAI-compatible base URL and the model IDs before starting the web app:

```sh
CONTROLGUARD_MODEL_URL=http://127.0.0.1:8000/v1 \
CONTROLGUARD_MODEL_A1=controlguard-a1 CONTROLGUARD_MODEL_A2=controlguard-a2 \
python -m controlguard web --port 8765
```

Use the IDs your server exposes, or set `CONTROLGUARD_MODEL` for both groups. Enable OpenAI-style function calls and JSON Schema responses on the server. For example, vLLM can serve compatible LoRA adapters with `--enable-lora`, `--lora-modules`, and Qwen/Hermes tool calling with `--enable-auto-tool-choice --tool-call-parser hermes`. llama.cpp and Ollama must expose the same capabilities for the chosen release and model format; they may require adapter format conversion. The HTTP test uses a mock endpoint, not vLLM, llama.cpp or Ollama.

The panel limits the tools the model can call. It validates tool arguments and runs calculations in Python. It never gives the model ledger access or lets the model's prose stand in for an engine result. It removes common SSN, account, email, phone and address patterns before each request. Pattern matching misses some personal data and may remove valid numbers. Do not submit real personal data. The local server may log requests. The HTTP client connects only to numeric loopback addresses and does not follow redirects. Neither the panel nor the ledger implements production authentication.

## Generate and train the adapters

A1 trains policy drafting and screening, title formatting and shift-based leave conversion. A2 trains tool use for triage, duty conflicts, and pricing. The generator writes chat JSONL with tool schemas, tool calls, deterministic tool results, and separate synthetic evaluation rows. The trainer supervises the first tool call, not model-generated arithmetic. The evaluation scores JSON validity, correct tool name and exact arguments. It does not measure legal correctness or generalization to real contracts.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install 'torch==2.7.1+cpu' --extra-index-url https://download.pytorch.org/whl/cpu
python -m pip install transformers==4.56.2 trl==0.23.1 peft==0.17.1 datasets==4.0.0
python -m controlguard.llm.dataset --train-count 64 --eval-count 12
python -m controlguard.llm.train llm-config/smoke-a1.json --output llm-output/smoke-a1
python -m controlguard.llm.train llm-config/smoke-a2.json --output llm-output/smoke-a2
```

Use the Qwen3-0.6B configs for CPU smoke tests. The trainer saves safetensors LoRA weights, predictions and before/after metrics under the chosen output directory. To rescore a prediction file against its four smoke rows, use `python -m controlguard.llm.evaluate EXPECTED.jsonl PREDICTIONS.jsonl --limit 4`.

The GPU configs target Qwen3-8B and Qwen3-32B. The trainer pins each base revision, blocks models outside the allowlist, verifies safetensors header bounds and offsets, and checks the chat template against a reviewed hash and blocked tokens. It uses neither remote code nor pickle weights. Use the synthetic generator, not unreviewed third-party corpora.

Preview a single Qwen3-8B job without spending:

```sh
python scripts/hf_job.py --adapter a1 --private-model-repo OWNER/REPO
```

The recipe requests one 24 GB A10G, 250 steps per adapter, and a four-hour limit. Budget 1–3 hours per adapter as an estimate, not a benchmark. [Hugging Face lists an hourly rate of $1.50](https://huggingface.co/docs/hub/en/jobs-pricing). At that rate, 1–3 hours costs $1.50–$4.50. The four-hour limit caps compute charges at $6. The separate `--launch` option starts paid compute and requires an authenticated Hugging Face account and private repository access. No job ran as part of this delivery.

## Verify the code

```sh
python -m pip install 'pytest>=8,<10' 'mypy>=1.11,<3'
python -m pytest -q
python -m mypy --strict
```

The checks do not download a model or access the network outside the loopback test server.
