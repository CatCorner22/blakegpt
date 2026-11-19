import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.doUnmock("better-auth/react");
});

async function loadClient() {
  vi.resetModules();
  vi.doMock("better-auth/react", () => ({ createAuthClient: () => ({}) }));
  return import("./client");
}

describe("signInErrorMessage", () => {
  it("explains an expired confirmation or password link", async () => {
    const { signInErrorMessage } = await loadClient();
    for (const code of ["TOKEN_EXPIRED", "INVALID_TOKEN", "USER_NOT_FOUND"]) {
      expect(signInErrorMessage(code)).toMatch(
        /^That link has expired, or someone already used it/,
      );
    }
  });

  it("names an unrecognized error code", async () => {
    const { signInErrorMessage } = await loadClient();
    expect(signInErrorMessage("state_mismatch")).toBe(
      'Precog could not finish the sign-in (code "state_mismatch"). Try again in a moment.',
    );
  });
});
