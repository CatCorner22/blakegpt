#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 1 ]]; then
  printf 'Usage: bash backup.sh PATH_TO_NEW_DUMP\n' >&2
  exit 1
fi
: "${DATABASE_URL:?Set DATABASE_URL to the Precog PostgreSQL database.}"

umask 077
dump=$(mktemp -- "${1}.partial.XXXXXX")
trap 'rm -f -- "$dump"' EXIT
node -e '
  const { spawnSync } = require("node:child_process");
  let url, password;
  try {
    url = new URL(process.env.DATABASE_URL);
    if (!["postgresql:", "postgres:"].includes(url.protocol)) throw new Error();
    password = url.searchParams.get("password") ?? decodeURIComponent(url.password);
    url.password = "";
    url.searchParams.delete("password");
  } catch {
    console.error("DATABASE_URL must be a PostgreSQL connection URL.");
    process.exit(1);
  }
  const result = spawnSync("pg_dump", [
    "--no-password", "--format=custom", "--dbname", url.href, "--file", process.argv[1],
  ], {
    stdio: "inherit",
    env: { ...process.env, ...(password ? { PGPASSWORD: password } : {}) },
  });
  if (result.error) console.error(result.error.message);
  process.exit(result.status ?? 1);
' "$dump"
ln -T -- "$dump" "$1"
printf 'Precog backup saved to %s\n' "$1"
