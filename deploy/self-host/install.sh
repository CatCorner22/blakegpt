#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID != 0 ]]; then
  printf 'Run this installer with sudo.\n' >&2
  exit 1
fi
cd /opt/precog

if [[ ! -x /usr/bin/node || ! -f .output/server/index.mjs ]]; then
  printf 'Install Node 22 at /usr/bin/node and build Precog for node-server first.\n' >&2
  exit 1
fi

if ! id precog >/dev/null 2>&1; then
  useradd --system --user-group --home-dir /opt/precog --shell /usr/sbin/nologin precog
fi
install -d -m 0750 -o root -g precog /etc/precog
install -d -m 0700 -o precog -g precog /var/lib/precog-backups
if [[ ! -f /etc/precog/precog.env ]]; then
  printf 'Create /etc/precog/precog.env as described in docs/SELF_HOSTING.md and run this again.\n' >&2
  exit 1
fi
chown root:precog /etc/precog/precog.env
chmod 0640 /etc/precog/precog.env

runuser -u precog -- /usr/bin/node --env-file=/etc/precog/precog.env -e '
  if (!process.env.DATABASE_URL || !process.env.BETTER_AUTH_URL ||
      (process.env.BETTER_AUTH_SECRET ?? "").length < 32 ||
      !/^[a-zA-Z0-9._~+/-]+=*$/.test(process.env.CRON_SECRET ?? "")) {
    throw new Error("Set DATABASE_URL, BETTER_AUTH_URL, BETTER_AUTH_SECRET and CRON_SECRET.");
  }
'
runuser -u precog -- /usr/bin/node --env-file=/etc/precog/precog.env scripts/migrate.mjs

units=(precog.service precog-digest.service precog-digest.timer)
if [[ -s /etc/precog/tunnel.token ]]; then
  if [[ ! -x /usr/bin/cloudflared ]]; then
    printf 'Install cloudflared at /usr/bin/cloudflared before enabling the tunnel.\n' >&2
    exit 1
  fi
  chown root:root /etc/precog/tunnel.token
  chmod 0600 /etc/precog/tunnel.token
  units+=(precog-tunnel.service)
fi
for unit in "${units[@]}"; do
  install -m 0644 "deploy/self-host/$unit" /etc/systemd/system/
done
systemctl daemon-reload
systemctl enable precog.service precog-digest.timer
systemctl restart precog.service precog-digest.timer
if [[ -s /etc/precog/tunnel.token ]]; then
  systemctl enable precog-tunnel.service
  systemctl restart precog-tunnel.service
elif [[ -f /etc/systemd/system/precog-tunnel.service ]]; then
  systemctl disable --now precog-tunnel.service
fi
