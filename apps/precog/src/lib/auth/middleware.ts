import { createMiddleware } from "@tanstack/react-start";
import { identitySnapshot, identityUnchanged } from "./identity-change";
import {
  ACCOUNT_CHANGED_MESSAGE,
  ACCOUNT_CHANGED_NOTHING_SAVED,
  assertExpectedAccount,
} from "./expected-account";

/**
 * Auth middleware for server functions — the standard way to get the caller's
 * verified user id. The same-origin session cookie rides along automatically.
 *
 *   import { createServerFn } from "@tanstack/react-start";
 *   import { getSql } from "@/lib/db";
 *   import { authMiddleware } from "@/lib/auth/middleware";
 *
 *   export const listTodos = createServerFn({ method: "GET" })
 *     .middleware([authMiddleware])
 *     .handler(async ({ context }) => {
 *       const sql = await getSql();
 *       return sql`select * from todos where user_id = ${context.userId}`;
 *     });
 *
 * Signed out (auth on — the default) -> throws
 * `UnauthorizedError` (see `verify.server.ts`). Only when auth is explicitly
 * disabled (`VITE_AUTH_ENABLED=false`) does it resolve the shared dev user and
 * never throw. Use it on every server function that touches per-user data, and
 * scope every query by `context.userId`.
 */
export const authMiddleware = createMiddleware({ type: "function" })
  .client(async ({ next }) => {
    const identity = identitySnapshot();
    if (!identityUnchanged(identity)) throw new Error(ACCOUNT_CHANGED_NOTHING_SAVED);
    const result = await next({
      sendContext: {
        expectedAccountId: identity.accountId,
        checkAccount: true,
      },
    });
    // The answer belongs to the account this page showed when it asked.
    if (!identityUnchanged(identity)) throw new Error(ACCOUNT_CHANGED_MESSAGE);
    return result;
  })
  .server(async ({ next, context }) => {
    // ONLY import `*.server` modules here. A plain `./isolation` path was
    // renamed to `isolation.server.ts` — keep this import in sync so image `tsc`
    // resolves it, and so Vite does not ship `@tanstack/react-start/server` to
    // the browser.
    const { assertSameSiteRequest } = await import("./isolation.server");
    const { requireUserId } = await import("./verify.server");
    // Reject scripted cross-site/sibling requests before touching per-user data.
    assertSameSiteRequest();
    const userId = await requireUserId();
    if (context.checkAccount) assertExpectedAccount(context.expectedAccountId, userId);
    return next({ context: { userId } });
  });
