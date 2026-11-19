import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

/**
 * Email/password sign-up against Precog's real Better Auth instance
 * (PGlite-backed).
 */
type Auth = (typeof import("./server"))["auth"];
let auth: Auth;

beforeAll(async () => {
  vi.stubEnv("DATABASE_URL", "");
  vi.stubEnv("VITE_AUTH_ENABLED", "true");
  ({ auth } = await import("./server"));
}, 60_000);

afterAll(() => {
  vi.unstubAllEnvs();
});

describe("email/password authentication", () => {
  it(
    "keeps an unconfirmed sign-up made while Precog cannot send email",
    { timeout: 60_000 },
    async () => {
      const { user, token } = await auth.api.signUpEmail({
        body: { email: "nomail@dental.example", password: "long-password-1", name: "No mail" },
      });
      expect(token).toBeTruthy();
      const { getSql } = await import("@/lib/db");
      const sql = await getSql();
      const kept = await sql`select 1 from unverified_sign_up_kept where user_id = ${user.id}`;
      expect(kept).toHaveLength(1);
    },
  );
});
