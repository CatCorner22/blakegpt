#!/usr/bin/env bash
set -euo pipefail

if [[ ! ${CRON_SECRET:-} =~ ^[A-Za-z0-9._~+/-]+=*$ ]]; then
  printf 'Set CRON_SECRET to a bearer token, for example with openssl rand -hex 32.\n' >&2
  exit 1
fi

printf 'Authorization: Bearer %s\n' "$CRON_SECRET" |
  curl --disable --noproxy '*' --fail --silent --show-error --max-time 300 \
    --header @- "http://127.0.0.1:${PORT:-8080}/api/cron/digest"
