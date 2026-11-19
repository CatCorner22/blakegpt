# BlakeGPT machine-learning features (Hugging Face)

All of these are light: small pretrained models, with no training required. They are for personal and professional use, and nothing critical depends on them. The verified cards stay the source of truth. Models help find and sort cards and documents; they never supply a legal fact.

| Feature | Model (Hugging Face) | Where it runs | What it does |
|---|---|---|---|
| Semantic search | `sentence-transformers/all-MiniLM-L6-v2` | CPU locally (sentence-transformers), or in the browser (Transformers.js) | Finds cards and documents by meaning ("when do we test the autoclave" → sterilization monitoring) |
| Re-ranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` | CPU locally | Orders the top 20 search hits by relevance |
| Auto-tagging | `facebook/bart-large-mnli` (zero-shot classification) | CPU locally, or HF Inference | Suggests a section (OSHA, privacy, employment and so on) for each ingested document |
| Summaries | Any small instruct model on an OpenAI-compatible endpoint (HF Inference router, Ollama, vLLM) | Local or hosted | Drafts the one-line summary for a new source; Amanda accepts or edits it |

## Guardrails
- Search results always show the card's citation and status. A model score never turns an unverified card into a verified one.
- Fallback: when no model is installed, search uses keyword matching (BM25), so every feature still works offline.
- Pin each model by name and revision in `tools/ml_config.json` once it is chosen, so results don't drift.
- The workspace runs text through `tools/pii_redact.py` before sending it to a model or saving it.
- No PII goes to any model. The workspace's privacy scan runs before ingestion.

## Optional fine-tuning (later, small)
If search misses Amanda's wording often, collect 50 to 200 question-and-card pairs from real use (no PII). Then fine-tune the embedding model briefly with sentence-transformers, for example `MultipleNegativesRankingLoss`, about 1 epoch on CPU or a free Colab GPU. Keep the old model and compare hit rates on a held-out 20% before switching.
