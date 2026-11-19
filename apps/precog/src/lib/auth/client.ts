import { createAuthClient } from "better-auth/react";
import {
  beginIdentityChange,
  cancelIdentityChange,
  currentExitCleanup,
  runExitCheck,
} from "./identity-change";

export const authClient = createAuthClient();

export const authEnabled = import.meta.env.VITE_AUTH_ENABLED !== "false";

export async function signOut(
  redirectTo = "/",
  options: { skipRecovery?: boolean } = {},
): Promise<void> {
  if (!options.skipRecovery && !(await runExitCheck("sign-out"))) return;
  const cleanup = currentExitCleanup();
  beginIdentityChange("signing-out");
  try {
    const result = await authClient.signOut();
    if (result.error) throw new Error(result.error.message ?? "Sign-out failed");
  } catch (error) {
    cancelIdentityChange();
    throw error;
  }
  try {
    cleanup?.();
  } catch {
    /* Failed storage cleanup must not restore an ended session. */
  }
  window.location.href = redirectTo;
}

export function signInErrorMessage(code: string): string {
  const normalized = code
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
  if (EXPIRED_LINK_CODES.has(normalized))
    return "That link has expired, or someone already used it. Sign in to get a new confirmation link, or use Forgot password for a new password link.";
  return `Precog could not finish the sign-in (code "${code.trim().slice(0, 80) || "sign_in_failed"}"). Try again in a moment.`;
}

const EXPIRED_LINK_CODES = new Set(["token_expired", "invalid_token", "user_not_found"]);
