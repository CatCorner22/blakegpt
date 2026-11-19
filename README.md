# office-compliance-assistant

## Layout

- `knowledge/federal/`: federal knowledge cards
- `knowledge/tennessee/`: Tennessee knowledge cards
- `muse/amanda/`: Muse project files
- `skills/`: portable skills and reference materials
- `tests/`: pytest tests and synthetic fixtures
- `tools/`: Python command-line tools and importable functions
- `.github/workflows/`: CI workflow

## Run tests and tools

Install the development dependency and run tests:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Run the tools from the repository root:

```sh
python -m tools.mscd_lint draft.txt --mode contract --party Company
python -m tools.leave_hours leave.csv --rate 30 --annual-cap 40 --balance-cap 80
python -m tools.expense_audit expenses.csv --threshold 5000 --window-hours 72
python -m tools.three_way_match purchase-orders.csv receipts.csv invoices.csv
python -m tools.oig_exclusion_check staff.csv --leie data/leie/UPDATED.csv
python -m tools.oig_exclusion_check staff.csv --download data/leie/UPDATED.csv
python -m tools.kb_freshness knowledge/
python -m tools.kb_freshness knowledge/ --federal-register
```

Each tool accepts `--json` for JSON output.
