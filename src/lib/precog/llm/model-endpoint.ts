/**
 * Where the coach's chat model lives. Defaults to xAI's Grok. Any server that
 * speaks the OpenAI chat-completions API (vLLM, TGI, Ollama, llama.cpp on a
 * GPU) can stand in by setting PRECOG_LLM_BASE_URL and PRECOG_LLM_MODEL; its
 * key goes in PRECOG_LLM_API_KEY. The model still only picks statement ids,
 * so a self-hosted model cannot add wording the rules did not write.
 */
export interface ModelEndpoint {
  url: string;
  model: string;
  apiKey: string;
  timeoutMs: number;
  provider: "xai" | "openai-compatible";
  /** The structured output to ask for first; see responseFormats. */
  responseFormat: ResponseFormatMode;
}

export type ResponseFormatMode = "json_schema" | "json_object" | "none";
const RESPONSE_FORMATS: readonly ResponseFormatMode[] = ["json_schema", "json_object", "none"];

const XAI_BASE_URL = "https://api.x.ai/v1";
const XAI_MODEL = "grok-4.5";
const DEFAULT_TIMEOUT_MS = 20_000;
const MAX_TIMEOUT_MS = 120_000;

export function modelEndpoint(
  env: Record<string, string | undefined> = process.env,
): ModelEndpoint {
  const base = env.PRECOG_LLM_BASE_URL?.trim().replace(/\/+$/, "");
  const custom = Boolean(base);
  const timeout = Number(env.PRECOG_LLM_TIMEOUT_MS);
  return {
    url: `${custom ? base : XAI_BASE_URL}/chat/completions`,
    model: env.PRECOG_LLM_MODEL?.trim() || XAI_MODEL,
    apiKey: (custom ? env.PRECOG_LLM_API_KEY : env.XAI_API_KEY)?.trim() ?? "",
    timeoutMs:
      Number.isFinite(timeout) && timeout > 0
        ? Math.min(timeout, MAX_TIMEOUT_MS)
        : DEFAULT_TIMEOUT_MS,
    provider: custom ? "openai-compatible" : "xai",
    responseFormat: responseFormatMode(env.PRECOG_LLM_RESPONSE_FORMAT, custom),
  };
}

function responseFormatMode(value: string | undefined, custom: boolean): ResponseFormatMode {
  const mode = value?.trim().toLowerCase() as ResponseFormatMode | undefined;
  if (mode && RESPONSE_FORMATS.includes(mode)) return mode;
  return custom ? "json_schema" : "json_object";
}

/** The key the configured endpoint needs; empty means the coach stays on its rules answer. */
export function modelApiKey(): string {
  return modelEndpoint().apiKey;
}
