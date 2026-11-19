---
name: ml-assist
description: Use BlakeGPT's light Hugging Face models to search, rank and tag the knowledge base and ingested documents by meaning (all-MiniLM-L6-v2 embeddings, a MiniLM cross-encoder re-ranker, bart-large-mnli zero-shot tags), with keyword fallback. Use when a keyword search misses, when tagging a new source, or when the user asks for semantic search, similar documents, or auto-tagging.
---

# ML assist

1. Search by meaning first (see `docs/MACHINE_LEARNING.md`), and show the top 5 cards with citation, status and score.
2. Never treat a score as evidence. Answer only from the card's quoted text (`dental-office-compliance-tn`).
3. When tagging a source, show the suggested section and its score, and let Amanda confirm it.
4. If no model is available, say so and use keyword search.
