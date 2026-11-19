/**
 * Whether Precog can use an account's address, as SQL fragments over a
 * `"user"` row aliased `alias` (a name the caller writes, never user input).
 */
export const VOUCHED_EMAIL = (alias: string) => `(${alias}."emailVerified")`;

/** The account address Precog may use for reminders and service notices. */
export const TRUSTED_EMAIL = VOUCHED_EMAIL;
