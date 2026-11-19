# Voyager on any model platform

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

On a custom endpoint Precog asks for the selection protocol as a JSON schema
(`response_format: json_schema`, ids limited to the claims on screen), which the
server enforces while decoding. A platform that answers 400 to that request
gets `json_object`, then no format; the strict parser checks every answer either
way. `PRECOG_LLM_RESPONSE_FORMAT` starts lower for a platform known to support
less. Without the schema a 1.5B model on CPU had 27 of 30 selections rejected
(a missing `version` field, evidence ids instead of statement ids). vLLM
rejected `uniqueItems`, so the schema uses only keywords common grammar engines
implement.

## Platforms

Each base URL below answered a chat-completions request with an authentication
error (not a missing route) on 2026-11-19, so the same three settings switch
Precog between them. Only the self-hosted vLLM and Ollama rows have been run
end to end.

| Platform            | `PRECOG_LLM_BASE_URL`                                     |
| ------------------- | --------------------------------------------------------- |
| vLLM, TGI (any GPU) | `http://<host>:8000/v1`                                   |
| Ollama              | `http://<host>:11434/v1`                                  |
| Meta Llama API      | `https://api.llama.com/compat/v1`                         |
| Google Gemini       | `https://generativelanguage.googleapis.com/v1beta/openai` |
| Anthropic Claude    | `https://api.anthropic.com/v1`                            |
| OpenAI              | `https://api.openai.com/v1`                               |
| Mistral             | `https://api.mistral.ai/v1`                               |
| OpenRouter          | `https://openrouter.ai/api/v1`                            |
| Groq                | `https://api.groq.com/openai/v1`                          |
| Together            | `https://api.together.xyz/v1`                             |
| Hugging Face router | `https://router.huggingface.co/v1`                        |

## Measured

| Model                    | Where         | Answered | Invalid ids | p50 / p95 latency |
| ------------------------ | ------------- | -------- | ----------- | ----------------- |
| qwen2.5:1.5b (Ollama)    | 8-core CPU    | 10 / 10  | 0           | 0.6 s (warm)      |
| Qwen/Qwen2.5-7B-Instruct | Colab L4 vLLM | 30 / 30  | 0           | 1.2 s / 1.6 s     |

Both injection prompts in each industry returned only on-screen ids. The 7B
model picked the first statement in 23 of 30 cases (5 distinct selections), so
the selections are safe but not yet discriminating; compare larger models with
the same evaluation before choosing one.

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
