import { expect, it, vi } from "vitest";

const seams = vi.hoisted(() => ({
  access: { userId: "u1", grok: "rate_limited" },
  spend: vi.fn().mockResolvedValue({ budget: "allowed" }),
  extract: vi.fn(),
}));

vi.mock("@tanstack/react-start", () => ({
  createServerFn: () => {
    const chain = {
      middleware: () => chain,
      validator: () => chain,
      handler:
        (handler: (input: { data: unknown; context: { llm: typeof seams.access } }) => unknown) =>
        ({ data }: { data?: unknown }) =>
          handler({ data, context: { llm: seams.access } }),
    };
    return chain;
  },
}));
vi.mock("./middleware", () => ({ heavyLlmMiddleware: {} }));
vi.mock("./guard.server", () => ({ spendCallerDailyUnit: seams.spend }));
vi.mock("./controlguard-provider.server", () => ({
  controlguardProvider: () => ({ model: "combined" }),
  extractControlGuardInput: seams.extract,
}));

import { extractControlGuardFacts } from "./controlguard-server";

it("keeps a rate-limited draft on the manual path without spending a model unit", async () => {
  await expect(
    extractControlGuardFacts({ data: { prompt: "Find the notice date." } }),
  ).resolves.toBeNull();
  expect(seams.spend).not.toHaveBeenCalled();
  expect(seams.extract).not.toHaveBeenCalled();
});
