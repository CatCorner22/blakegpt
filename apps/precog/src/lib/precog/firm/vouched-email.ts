/**
 * Whether Precog can use an account's address, as SQL fragments over a
 * `"user"` row aliased `alias` (a name the caller writes, never user input).
 * The firm join and notices exclude synthetic addresses from legacy sign-ins.
 */
export const isLegacySyntheticEmail = (alias: string) => `(
  exists (
    select 1 from account a
    where a."userId" = ${alias}.id and right(a."providerId", 2) = '-x'
  )
  and not (
    exists (
      select 1 from account a
      where a."userId" = ${alias}.id and a."providerId" = 'credential'
    )
    or exists (
      select 1 from account a
      where a."userId" = ${alias}.id and right(a."providerId", 7) = '-google'
    )
  )
)`;

export const VOUCHED_EMAIL = (alias: string) =>
  `(${alias}."emailVerified" and not ${isLegacySyntheticEmail(alias)})`;

/** The account address Precog may use for reminders and service notices. */
export const TRUSTED_EMAIL = VOUCHED_EMAIL;
