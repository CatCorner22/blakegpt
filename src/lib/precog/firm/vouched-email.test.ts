import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { openTestDb, type TestDb } from "@/test/pglite";
import { digestAddressProblem, trustedEmailAddress } from "./store";
import { TRUSTED_EMAIL, VOUCHED_EMAIL } from "./vouched-email";

const ACCOUNTS = [
  { id: "confirmed", verified: true, providers: ["credential"] },
  { id: "unconfirmed", verified: false, providers: ["credential"] },
  { id: "legacy_synthetic", verified: true, providers: ["legacy-x"] },
  { id: "legacy_google", verified: true, providers: ["legacy-google"] },
];

describe("vouched addresses", () => {
  let db: TestDb;

  beforeAll(async () => {
    db = await openTestDb();
    for (const account of ACCOUNTS) {
      await db.seedUser(account.id, `${account.id}@example.test`);
      await db.pg.query(`update "user" set "emailVerified" = $2 where id = $1`, [
        account.id,
        account.verified,
      ]);
      for (const providerId of account.providers) {
        await db.pg.query(
          `insert into account (id, "accountId", "providerId", "userId", "createdAt", "updatedAt")
           values ($1, $2, $3, $4, now(), now())`,
          [`${account.id}_${providerId}`, account.id, providerId, account.id],
        );
      }
    }
  }, 60_000);

  afterAll(async () => {
    await db.close();
  });

  async function verdicts(fragment: (alias: string) => string): Promise<Record<string, boolean>> {
    const rows = await db.sql.query<{ id: string; ok: boolean }>(
      `select u.id, ${fragment("u")} as ok from "user" u order by u.id`,
    );
    return Object.fromEntries(rows.map((row) => [row.id, row.ok]));
  }

  it("does not vouch for a verified synthetic legacy address", async () => {
    const expected = {
      confirmed: true,
      legacy_google: true,
      legacy_synthetic: false,
      unconfirmed: false,
    };
    expect(await verdicts(VOUCHED_EMAIL)).toEqual(expected);
    expect(await verdicts(TRUSTED_EMAIL)).toEqual(expected);
  });

  it("sends notices only to a confirmed email address", async () => {
    expect(await digestAddressProblem(db.sql, "confirmed")).toBeNull();
    expect(await digestAddressProblem(db.sql, "unconfirmed")).toBe("unconfirmed");
    expect(await digestAddressProblem(db.sql, "legacy_synthetic")).toBe("unconfirmed");
    expect(await digestAddressProblem(db.sql, "nobody")).toBeNull();
    expect(await trustedEmailAddress(db.sql, "confirmed")).toBe("confirmed@example.test");
    expect(await trustedEmailAddress(db.sql, "unconfirmed")).toBeNull();
    expect(await trustedEmailAddress(db.sql, "legacy_synthetic")).toBeNull();
    expect(await trustedEmailAddress(db.sql, "nobody")).toBeNull();
  });
});
