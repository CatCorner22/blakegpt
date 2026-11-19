# Testing Voyager on a GPU model

Voyager's model never writes the words an owner reads. It picks up to three
ids of statements the rules engine already wrote, and Precog renders those
statements itself. Any chat model behind an OpenAI-compatible API can do that
job, so a self-hosted model on a GPU can stand in for xAI.

## Settings

| Variable                | Meaning                                                                                   |
| ----------------------- | ----------------------------------------------------------------------------------------- |
| `PRECOG_LLM_BASE_URL`   | Base URL ending in `/v1` (for example `http://gpu-box:8000/v1`). Empty: xAI.              |
| `PRECOG_LLM_MODEL`      | Model name the server serves (for example `Qwen/Qwen2.5-7B-Instruct`). Empty: `grok-4.5`. |
| `PRECOG_LLM_API_KEY`    | Key for that server. The xAI key is never sent to a custom URL.                           |
| `PRECOG_LLM_TIMEOUT_MS` | Per-call timeout, default 20000, at most 120000.                                          |

With no key for the configured endpoint, Voyager answers from its rules, as it
does today without `XAI_API_KEY`.

On a custom endpoint Precog sends the selection protocol as a JSON schema
(`response_format: json_schema`, ids limited to the claims on screen). vLLM,
TGI, Ollama and llama.cpp enforce it while decoding. Without it, a 1.5B model
on CPU had 27 of 30 selections rejected (a missing `version` field, evidence
ids instead of statement ids); with it, 10 of 10 parsed.

## Start a server

- **Colab (Pro: L4 or A100).** Upload `docs/gpu/precog-gpu-colab.ipynb`, choose
  a GPU runtime and Run all. The last cell prints the three settings. The
  address lasts as long as the notebook session.
- **Any Linux GPU box.**
  `vllm serve Qwen/Qwen2.5-7B-Instruct --api-key <key> --max-model-len 8192`
- **CPU smoke test.**
  `docker run -d -p 11434:11434 ollama/ollama`, then
  `ollama pull qwen2.5:1.5b`; base URL `http://localhost:11434/v1`, any key.

## Run the evaluation

```sh
PRECOG_LLM_BASE_URL=... PRECOG_LLM_MODEL=... PRECOG_LLM_API_KEY=... npm run eval:llm
```

`src/lib/precog/llm/model-eval.live.test.ts` runs Voyager's real prompt for
eight owner questions and two prompt-injection attempts in each of three
sample industries (`PRECOG_LLM_EVAL_INDUSTRIES` changes them), through
Precog's own strict parser. It fails when any selection names an id that is
not on screen, when any call does not reach the model, or when fewer than
`PRECOG_LLM_EVAL_MIN_ANSWERED` (default 0.8) of the cases are answered. The
JSON report in `artifacts/llm-eval/` lists, for each case, the status, the
selected statements, the raw reply, the tokens and the latency, plus p50/p95
latency, completion tokens per second and how many distinct selections the
model made. `npm test` skips this file.
