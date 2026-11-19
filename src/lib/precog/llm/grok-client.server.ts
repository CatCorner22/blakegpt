import { modelEndpoint } from "./model-endpoint";

export interface GrokChatOptions {
  messages: {
    role: "system" | "user" | "assistant";
    content: string;
  }[];
  maxTokens: number;
  temperature: number;
  jsonObject?: boolean;
  /**
   * A JSON schema a self-hosted server (vLLM, TGI, Ollama) enforces while it
   * decodes, so a small model cannot drop a field or name an unknown id.
   * Sent only to an OpenAI-compatible endpoint; xAI keeps json_object.
   */
  jsonSchema?: { name: string; schema: Record<string, unknown> };
  /** Which feature made the call, for the usage log line only; never sent upstream. */
  feature?: string;
  /**
   * Receives the same usage line the log gets, for every attempted call
   * (success or failure), so the caller can store it. Never sent upstream.
   */
  onUsage?: (line: GrokUsageLine) => void;
}

export interface GrokChatResult {
  text: string;
  model: string;
}

/** One structured log line per model call: no prompt text, no key. */
export interface GrokUsageLine {
  feature: string;
  model: string;
  promptTokens: number | null;
  completionTokens: number | null;
  totalTokens: number | null;
  latencyMs: number;
  outcome: "ok" | "empty" | "timeout" | "error" | `http_${number}`;
}

/**
 * One chat call to the model. Returns null on any upstream failure so callers
 * can use their local fallback, and logs why (status, timeout or network
 * error) without the request body or the key. Every attempted call also logs
 * one `[grok] usage` line with the tokens the API reports, so spend per
 * feature can be read from the logs.
 */
export async function grokChat(
  apiKey: string,
  opts: GrokChatOptions,
): Promise<GrokChatResult | null> {
  if (!apiKey.trim()) return null;
  const endpoint = modelEndpoint();

  const body: {
    model: string;
    max_tokens: number;
    temperature: number;
    messages: GrokChatOptions["messages"];
    response_format?:
      | { type: "json_object" }
      | {
          type: "json_schema";
          json_schema: { name: string; strict: true; schema: Record<string, unknown> };
        };
  } = {
    model: endpoint.model,
    max_tokens: opts.maxTokens,
    temperature: opts.temperature,
    messages: opts.messages,
  };
  if (opts.jsonSchema && endpoint.provider === "openai-compatible") {
    body.response_format = {
      type: "json_schema",
      json_schema: { name: opts.jsonSchema.name, strict: true, schema: opts.jsonSchema.schema },
    };
  } else if (opts.jsonObject) body.response_format = { type: "json_object" };

  const started = Date.now();
  const usage = (
    outcome: GrokUsageLine["outcome"],
    model: string,
    tokens?: { prompt_tokens?: unknown; completion_tokens?: unknown; total_tokens?: unknown },
  ) => {
    const line: GrokUsageLine = {
      feature: opts.feature ?? "unknown",
      model,
      promptTokens: tokenCount(tokens?.prompt_tokens),
      completionTokens: tokenCount(tokens?.completion_tokens),
      totalTokens: tokenCount(tokens?.total_tokens),
      latencyMs: Date.now() - started,
      outcome,
    };
    logUsage(line);
    try {
      opts.onUsage?.(line);
    } catch {
      // A recorder that throws never changes the call's answer.
    }
  };

  try {
    const response = await fetch(endpoint.url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(endpoint.timeoutMs),
    });
    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      console.error(`[grok] upstream ${response.status}: ${redact(detail).slice(0, 300)}`);
      usage(`http_${response.status}`, endpoint.model);
      return null;
    }
    const result = (await response.json()) as {
      choices?: { message?: { content?: string } }[];
      model?: string;
      usage?: { prompt_tokens?: unknown; completion_tokens?: unknown; total_tokens?: unknown };
    };
    const model = result.model?.trim() || endpoint.model;
    const text = result.choices?.[0]?.message?.content?.trim();
    if (!text) {
      console.error("[grok] upstream returned no text");
      usage("empty", model, result.usage);
      return null;
    }
    usage("ok", model, result.usage);
    return { text, model };
  } catch (error) {
    const name = error instanceof Error ? error.name : "Error";
    const timedOut = name === "TimeoutError" || name === "AbortError";
    usage(timedOut ? "timeout" : "error", endpoint.model);
    console.error(
      timedOut
        ? `[grok] no answer within ${endpoint.timeoutMs / 1000}s`
        : `[grok] request failed: ${name}: ${redact(error instanceof Error ? error.message : String(error))}`,
    );
    return null;
  }
}

function tokenCount(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function logUsage(line: GrokUsageLine): void {
  console.info(`[grok] usage ${JSON.stringify(line)}`);
}

/** Masks anything shaped like an API key, in case an upstream error echoes one. */
function redact(text: string): string {
  return text
    .replace(/xai-[A-Za-z0-9_-]+/g, "xai-…")
    .replace(/(Bearer\s+)[A-Za-z0-9._~+/=-]+/gi, "$1…")
    .replace(/\b(hf|sk)[-_][A-Za-z0-9_-]{8,}/g, "$1-…");
}
