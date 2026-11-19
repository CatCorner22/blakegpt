/**
 * The optional business-configured model server. Without a base URL, callers
 * use their existing rules-based fallback.
 */
export interface ModelEndpoint {
  url: string;
  model: string;
  apiKey: string;
  timeoutMs: number;
  /** The structured output to ask for first; see responseFormats. */
  responseFormat: ResponseFormatMode;
}

export type ResponseFormatMode = "json_schema" | "json_object" | "none";
const RESPONSE_FORMATS: readonly ResponseFormatMode[] = ["json_schema", "json_object", "none"];
const DEFAULT_TIMEOUT_MS = 20_000;
const MAX_TIMEOUT_MS = 120_000;

export function modelEndpoint(
  env: Record<string, string | undefined> = process.env,
): ModelEndpoint | null {
  const base = env.PRECOG_LLM_BASE_URL?.trim().replace(/\/+$/, "");
  if (!base) return null;
  const timeout = Number(env.PRECOG_LLM_TIMEOUT_MS);
  return {
    url: `${base}/chat/completions`,
    model: env.PRECOG_LLM_MODEL?.trim() ?? "",
    apiKey: env.PRECOG_LLM_API_KEY?.trim() ?? "",
    timeoutMs:
      Number.isFinite(timeout) && timeout > 0
        ? Math.min(timeout, MAX_TIMEOUT_MS)
        : DEFAULT_TIMEOUT_MS,
    responseFormat: responseFormatMode(env.PRECOG_LLM_RESPONSE_FORMAT),
  };
}

function responseFormatMode(value: string | undefined): ResponseFormatMode {
  const mode = value?.trim().toLowerCase() as ResponseFormatMode | undefined;
  return mode && RESPONSE_FORMATS.includes(mode) ? mode : "json_schema";
}

/** The key for the configured endpoint, or an empty string when it needs none. */
export function modelApiKey(): string {
  return modelEndpoint()?.apiKey ?? "";
}
