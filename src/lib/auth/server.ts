/**
 * Precog's self-hosted Better Auth configuration (server-only).
 *
 * Email/password sign-in for Precog.
 *
 * Precog runs Better Auth at `/api/auth/*`, so the session cookie stays on
 * Precog's own origin. People sign in with a Precog email/password account.
 *
 * Deployed auth uses BETTER_AUTH_URL, BETTER_AUTH_SECRET and DATABASE_URL.
 * Local development uses the embedded PGLite database and a process-stable
 * secret. `VITE_AUTH_ENABLED=false` disables auth and lets server functions
 * fall back to a dev user (see `verify.server.ts`).
 *
 * NEVER import this from client code — it pulls in `pg`, the auth secret and
 * server-only Better Auth internals. The client uses `@/lib/auth/client`;
 * components read the user via `@/lib/auth/use-current-user`; server functions get
 * a verified id via `@/lib/auth/middleware`.
 */
import { betterAuth } from "better-auth";
import { tanstackStartCookies } from "better-auth/tanstack-start";
import { randomBytes } from "node:crypto";
import { PostgresDialect } from "kysely";
import { databaseConfigured, getPglite, getPgPool } from "../db";
import { emailAndPasswordEnabled, PASSWORD_MIN_LENGTH } from "./email-password";
import { emailPasswordExtras, emailVerificationOptions } from "./email-password.server";
import { pgliteDialect } from "./pglite-dialect";

/**
 * The local secret must outlive module reloads: PGLite and its session rows are
 * stored on `globalThis`, so an HMR re-eval must not invalidate an active
 * session. A process restart clears both together.
 */
const globalAuthRef = globalThis as typeof globalThis & {
  __precogAuthSecret__?: string;
};
function localAuthSecret(): string {
  globalAuthRef.__precogAuthSecret__ ??= randomBytes(32).toString("hex");
  return globalAuthRef.__precogAuthSecret__;
}

/** Read an env var, treating empty/whitespace as unset. */
const env = (key: string): string | undefined => {
  const value = process.env[key]?.trim();
  return value ? value : undefined;
};

// Explicit off-switch for local development without an authenticated account.
const authDisabled = env("VITE_AUTH_ENABLED") === "false";

/** True when Precog enforces real account sign-in. */
export const authConfigured = !authDisabled;

// Deployed apps set their public origin; local development defaults to port 8080.
const explicitBaseURL = env("BETTER_AUTH_URL");
// Local `npm run dev` (port 8080 contract). Browsers may send Origin as any of
// these for the same server — trusting only `localhost` rejects `127.0.0.1` and
// breaks email/password with "Invalid origin".
const LOCAL_DEV_ORIGINS: string[] = [
  "http://localhost:8080",
  "http://127.0.0.1:8080",
  "http://[::1]:8080",
];
const baseURL = explicitBaseURL ?? "http://localhost:8080";

// Origins Better Auth accepts on credentialed POSTs (sign-up/sign-in, etc.).
// Missing entries here surface as FORBIDDEN "Invalid origin". A deployed app
// trusts only its own public URL; the loopback variants join only when that
// URL is itself a local one.
const trustedOrigins: string[] = explicitBaseURL
  ? LOCAL_DEV_ORIGINS.includes(explicitBaseURL.replace(/\/+$/, ""))
    ? [explicitBaseURL, ...LOCAL_DEV_ORIGINS]
    : [explicitBaseURL]
  : LOCAL_DEV_ORIGINS;

// Real Postgres when `DATABASE_URL` is set, else Precog's embedded PGLite
// via a Kysely dialect — so Better Auth persists to the
// SAME DB as app data, including email/password users. Both use the Better Auth
// schema from `migrations/0001_auth.sql`. The Postgres path shares the app's
// one pool (`getPgPool`) instead of opening a second per instance.
const database = databaseConfigured
  ? { dialect: new PostgresDialect({ pool: () => getPgPool() }), type: "postgres" as const }
  : { dialect: pgliteDialect(() => getPglite()), type: "postgres" as const };

/** Session token cookie name. */
export const SESSION_TOKEN_COOKIE = "__Host-precog-auth.session_token";

export const auth = betterAuth({
  baseURL,
  // Deployed apps inject BETTER_AUTH_SECRET. Preview: process-stable secret on
  // globalThis so HMR doesn't invalidate PGLite-backed sessions (see above).
  secret: env("BETTER_AUTH_SECRET") ?? localAuthSecret(),
  database,

  // CSRF / origin check for credentialed auth POSTs (email sign-up/sign-in, …).
  // See `trustedOrigins` construction above — must cover preview hosts AND
  // local loopback variants, or clients get "Invalid origin".
  trustedOrigins,

  // Cache the session in the short-lived signed `session_data` cookie so reads
  // (incl. the client's `/get-session`) skip the DB — this shrinks the "loading"
  // window and reduces auth flicker.
  session: { cookieCache: { enabled: true, maxAge: 300 } },

  // Password guessing: at most five email sign-in or sign-up attempts per
  // minute from one network address. Better Auth keeps the counter in memory,
  // so each serverless instance counts on its own.
  rateLimit: {
    customRules: {
      "/sign-in/email": { window: 60, max: 5 },
      "/sign-up/email": { window: 60, max: 5 },
    },
  },

  // Local email/password — toggled only via `./email-password` (not a plugin).
  ...(emailAndPasswordEnabled
    ? {
        emailAndPassword: {
          enabled: true,
          minPasswordLength: PASSWORD_MIN_LENGTH,
          ...emailPasswordExtras,
        },
        ...emailVerificationOptions,
      }
    : {}),

  // `__Host-` requires Secure + Path=/ + no Domain; Better Auth otherwise uses
  // `__Secure-` (which permits Domain), so set Secure and the names ourselves.
  // Browsers allow Secure cookies on `http://localhost` for local development.
  advanced: {
    useSecureCookies: false,
    defaultCookieAttributes: { secure: true, sameSite: "lax", path: "/" },
    cookies: {
      session_token: { name: SESSION_TOKEN_COOKIE },
      session_data: { name: "__Host-precog-auth.session_data" },
      account_data: { name: "__Host-precog-auth.account_data" },
      dont_remember: { name: "__Host-precog-auth.dont_remember" },
    },
  },

  plugins: [tanstackStartCookies()],
});
