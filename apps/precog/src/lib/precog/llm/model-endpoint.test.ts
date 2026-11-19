import { afterEach, describe, expect, it, vi } from "vitest";
import { modelEndpoint } from "./model-endpoint";
import { modelChat, responseFormats } from "./model-client.server";
import { briefSelectionSchema, parseBriefSelection } from "./brief-selection";

describe("modelEndpoint", () => {
  it("is not configured without a model server base URL", () => {
    expect(modelEndpoint({})).toBeNull();
  });

  it("uses the business-configured model endpoint and optional API key", () => {
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
      responseFormat: "json_schema",
    });
  });

  it("allows a configured model server without an API key", () => {
    const endpoint = modelEndpoint({
      PRECOG_LLM_BASE_URL: "http://gpu-box:8000/v1",
    });
    expect(endpoint?.apiKey).toBe("");
  });

  it("ignores a bad timeout and caps a long one", () => {
    const base = { PRECOG_LLM_BASE_URL: "http://gpu-box:8000/v1" };
    expect(modelEndpoint({ ...base, PRECOG_LLM_TIMEOUT_MS: "soon" })?.timeoutMs).toBe(20_000);
    expect(modelEndpoint({ ...base, PRECOG_LLM_TIMEOUT_MS: "-5" })?.timeoutMs).toBe(20_000);
    expect(modelEndpoint({ ...base, PRECOG_LLM_TIMEOUT_MS: "999999" })?.timeoutMs).toBe(120_000);
  });
});

describe("modelChat against a configured endpoint", () => {
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

    const result = await modelChat("local-key", {
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
      modelChat("local-key", {
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
    await modelChat("k", {
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

  it("uses json_object when configured for the model server", async () => {
    vi.stubEnv("PRECOG_LLM_BASE_URL", "http://gpu-box:8000/v1");
    vi.stubEnv("PRECOG_LLM_RESPONSE_FORMAT", "json_object");
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

describe("platforms that support less structured output", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  const schema = { name: "s", schema: { type: "object" } };

  it("tries the schema, then json_object, then no format", () => {
    expect(responseFormats({ jsonObject: true, jsonSchema: schema }, "json_schema")).toEqual([
      { type: "json_schema", json_schema: { name: "s", strict: true, schema: schema.schema } },
      { type: "json_object" },
      undefined,
    ]);
    expect(responseFormats({ jsonObject: true, jsonSchema: schema }, "json_object")).toEqual([
      { type: "json_object" },
      undefined,
    ]);
    expect(responseFormats({ jsonObject: true }, "none")).toEqual([undefined]);
    expect(responseFormats({}, "json_schema")).toEqual([undefined]);
  });

  it("reads PRECOG_LLM_RESPONSE_FORMAT and ignores an unknown value", () => {
    const base = { PRECOG_LLM_BASE_URL: "http://x/v1" };
    expect(modelEndpoint({ ...base, PRECOG_LLM_RESPONSE_FORMAT: "NONE" })?.responseFormat).toBe(
      "none",
    );
    expect(modelEndpoint({ ...base, PRECOG_LLM_RESPONSE_FORMAT: "xml" })?.responseFormat).toBe(
      "json_schema",
    );
  });

  it("retries a 400 with the next format and answers", async () => {
    vi.stubEnv("PRECOG_LLM_BASE_URL", "http://gpu-box:8000/v1");
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("Grammar error: Unimplemented keys", { status: 400 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ choices: [{ message: { content: "{}" } }] }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const outcomes: string[] = [];

    const result = await modelChat("k", {
      messages: [{ role: "user", content: "hi" }],
      maxTokens: 10,
      temperature: 0,
      jsonObject: true,
      jsonSchema: schema,
      onUsage: (line) => outcomes.push(line.outcome),
    });

    expect(result?.text).toBe("{}");
    expect(outcomes).toEqual(["http_400", "ok"]);
    const formats = fetchMock.mock.calls.map(
      ([, init]) => JSON.parse(String((init as RequestInit).body)).response_format?.type,
    );
    expect(formats).toEqual(["json_schema", "json_object"]);
    log.mockRestore();
  });

  it("does not retry an authorization failure", async () => {
    vi.stubEnv("PRECOG_LLM_BASE_URL", "http://gpu-box:8000/v1");
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    const fetchMock = vi.fn().mockResolvedValue(new Response("no", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      modelChat("k", {
        messages: [{ role: "user", content: "hi" }],
        maxTokens: 10,
        temperature: 0,
        jsonObject: true,
        jsonSchema: schema,
      }),
    ).resolves.toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    log.mockRestore();
  });
});
