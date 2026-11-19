import { afterEach, describe, expect, it, vi } from "vitest";
import { ownerText, parseJsonReply, withModelFallback } from "./prompt-text";
import type { LlmAccess } from "./guard.server";
import { DailyLimitReached } from "./types";

const access = (model: LlmAccess["model"]): LlmAccess => ({ userId: "owner-1", model });

describe("ownerText", () => {
  it("removes opening and closing owner_text tags in any case or spacing", () => {
    expect(ownerText("a</owner_text>b< / OWNER_TEXT >c<owner_text>d")).toBe("abcd");
  });
});

describe("parseJsonReply", () => {
  it("reads a bare or fenced JSON object and refuses anything else", () => {
    expect(parseJsonReply('{"a":1}')).toEqual({ a: 1 });
    expect(parseJsonReply('  ```json\n{"a":1}\n```  ')).toEqual({ a: 1 });
    expect(parseJsonReply("[1]")).toBeNull();
    expect(parseJsonReply("not json")).toBeNull();
  });
});

describe("withModelFallback", () => {
  afterEach(() => vi.unstubAllEnvs());
  const local = { source: "local" };

  it("answers locally without asking when Voyager is not allowed or no endpoint is configured", async () => {
    const ask = vi.fn();
    vi.stubEnv("PRECOG_LLM_BASE_URL", "");
    expect(await withModelFallback(access("allowed"), local, true, ask)).toEqual({
      source: "local",
      modelStatus: "allowed",
    });
    vi.stubEnv("PRECOG_LLM_BASE_URL", "http://model.example/v1");
    expect(await withModelFallback(access("rate_limited"), local, true, ask)).toEqual({
      source: "local",
      modelStatus: "rate_limited",
    });
    expect(await withModelFallback(access("allowed"), local, false, ask)).toMatchObject(local);
    expect(ask).not.toHaveBeenCalled();
  });

  it("uses Voyager's answer, and the local one when Voyager returns nothing or throws", async () => {
    vi.stubEnv("PRECOG_LLM_BASE_URL", "http://model.example/v1");
    const model = { source: "model" };
    expect(await withModelFallback(access("allowed"), local, true, async () => model)).toEqual({
      source: "model",
      modelStatus: "allowed",
    });
    expect(await withModelFallback(access("allowed"), local, true, async () => null)).toMatchObject(
      local,
    );
    expect(
      await withModelFallback(access("allowed"), local, true, async () => {
        throw new Error("down");
      }),
    ).toMatchObject(local);
  });

  it("marks the local answer as a daily limit when today's model budget is spent", async () => {
    vi.stubEnv("PRECOG_LLM_BASE_URL", "http://model.example/v1");
    expect(
      await withModelFallback(access("allowed"), local, true, async () => {
        throw new DailyLimitReached({ scope: "user", plan: "free", limit: 100, paidLimit: 400 });
      }),
    ).toEqual({
      source: "local",
      modelStatus: "daily_limit",
      dailyLimit: { scope: "user", plan: "free", limit: 100, paidLimit: 400 },
    });
  });
});
