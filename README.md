# BlakeGPT

BlakeGPT is the master app. Precog is its compliance and internal-controls
part. Frontier GRC is ControlGuard. The Compliance desk holds Amanda's 246
cited Tennessee and federal cards.

## Repository layout

| Path | Purpose | Documentation and tests |
| --- | --- | --- |
| `apps/precog/` | Precog's business workspace and core app | `README.md`; tests in `src/` and `scripts/`; `npm run verify` |
| `modules/controlguard/` | Frontier GRC checks and tools | `README.md`; Python tests in `tests/` |
| `modules/compliance/` | Amanda's cited compliance cards and tools | `README.md`; Python tests in `tests/` |
| `design/` | Samurai Cat theme and approved Reverie references | Reference documents and artwork |
| `deploy/` | Server setup and operating notes | `README.md`; DigitalOcean files in `digitalocean/` |

Each code module has its own README and tests. Run its checks from that
module's directory; the module README describes its commands.

## Source histories

This is the combined copy of `CatCorner22/precog`,
`CatCorner22/controlguard`, and
`CatCorner22/office-compliance-assistant`. Git subtree imports retain the
histories of all three source repositories. The source repositories remain
independent; changes here do not alter them.

## Public repository notice

This repository is public. Do not add patient, client, staff, or other
personally identifying information, confidential business records, passwords,
access tokens, or private keys. Use synthetic information in examples and
tests.
