import { afterEach, describe, expect, it, vi } from "vitest";
import { modelEndpoint } from "./model-endpoint";
import { grokChat } from "./grok-client.server";
import { briefSelectionSchema, parseBriefSelection } from "./brief-selection";

describe("modelEndpoint", () => {
  it("defaults to xAI Grok with the xAI key and a 20 second timeout", () => {
    expect(modelEndpoint({ XAI_API_KEY: " xai-k " })).toEqual({
      url: "https://api.x.ai/v1/chat/completions",
      model: "grok-4.5",
      apiKey: "xai-k",
      timeoutMs: 20_000,
      provider: "xai",
    });
  });

  it("points at an OpenAI-compatible GPU server when a base URL is set", () => {
    expect(
      modelEndpoint({
        PRECOG_LLM_BASE_URL: "http://gpu-box:8000/v1/",
        PRECOG_LLM_MODEL: "Qwen/Qwen2.5-7B-Instruct",
        PRECOG_LLM_API_KEY: "local-key",
        PRECOG_LLM_TIMEOUT_MS: "45000",
      }),
    ).toEqual({
      url: "http://gpu-box:8000/v1/chat/completions",
      model: "Qwen/Qwen2.5-7B-Instruct",
      apiKey: "local-key",
      timeoutMs: 45_000,
      provider: "openai-compatible",
    });
  });

  it("never sends the xAI key to a custom server", () => {
    const endpoint = modelEndpoint({
      PRECOG_LLM_BASE_URL: "http://gpu-box:8000/v1",
      XAI_API_KEY: "xai-secret",
    });
    expect(endpoint.apiKey).toBe("");
  });

  it("ignores a bad timeout and caps a long one", () => {
    expect(modelEndpoint({ PRECOG_LLM_TIMEOUT_MS: "soon" }).timeoutMs).toBe(20_000);
    expect(modelEndpoint({ PRECOG_LLM_TIMEOUT_MS: "-5" }).timeoutMs).toBe(20_000);
    expect(modelEndpoint({ PRECOG_LLM_TIMEOUT_MS: "999999" }).timeoutMs).toBe(120_000);
  });
});

describe("grokChat against a configured endpoint", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("posts to the configured URL with the configured model", async () => {
    vi.stubEnv("PRECOG_LLM_BASE_URL", "http://gpu-box:8000/v1");
    vi.stubEnv("PRECOG_LLM_MODEL", "qwen2.5:7b");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ choices: [{ message: { content: "{}" } }] }), {
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await grokChat("local-key", {
      messages: [{ role: "user", content: "hi" }],
      maxTokens: 10,
      temperature: 0,
      jsonObject: true,
    });

    expect(result).toEqual({ text: "{}", model: "qwen2.5:7b" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://gpu-box:8000/v1/chat/completions");
    expect(JSON.parse(String(init.body))).toMatchObject({
      model: "qwen2.5:7b",
      response_format: { type: "json_object" },
    });
  });

  it("redacts bearer tokens and provider keys from a logged error", async () => {
    vi.stubEnv("PRECOG_LLM_BASE_URL", "http://gpu-box:8000/v1");
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response("rejected Bearer abc.def-123 and hf_abcdefghijk", { status: 401 }),
        ),
    );

    await expect(
      grokChat("local-key", {
        messages: [{ role: "user", content: "hi" }],
        maxTokens: 10,
        temperature: 0,
      }),
    ).resolves.toBeNull();
    const logged = log.mock.calls.flat().join(" ");
    expect(logged).not.toContain("abc.def-123");
    expect(logged).not.toContain("hf_abcdefghijk");
    log.mockRestore();
  });
});

describe("structured output", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  const schema = briefSelectionSchema([
    { id: "move-0", text: "First" },
    { id: "situation", text: "Now" },
  ]);

  async function sentFormat(): Promise<unknown> {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ choices: [{ message: { content: "{}" } }] }), {
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await grokChat("k", {
      messages: [{ role: "user", content: "hi" }],
      maxTokens: 10,
      temperature: 0,
      jsonObject: true,
      jsonSchema: schema,
    });
    return JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body))
      .response_format;
  }

  it("asks a self-hosted server to enforce the selection schema", async () => {
    vi.stubEnv("PRECOG_LLM_BASE_URL", "http://gpu-box:8000/v1");
    expect(await sentFormat()).toEqual({
      type: "json_schema",
      json_schema: { name: "brief_selection", strict: true, schema: schema.schema },
    });
  });

  it("keeps json_object for xAI", async () => {
    vi.stubEnv("PRECOG_LLM_BASE_URL", "");
    expect(await sentFormat()).toEqual({ type: "json_object" });
  });

  it("limits ids to the claims and matches what the strict parser accepts", () => {
    const items = (schema.schema.properties as Record<string, { items?: unknown }>).highlightIds
      .items;
    expect(items).toEqual({ type: "string", enum: ["move-0", "situation"] });
    const claims = [
      { id: "move-0", text: "First" },
      { id: "situation", text: "Now" },
    ];
    expect(parseBriefSelection('{"version":1,"highlightIds":["situation"]}', claims)).toEqual([
      "situation",
    ]);
  });
});
