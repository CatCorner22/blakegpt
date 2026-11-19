# Self-host Precog

This setup keeps one copy of Precog and PostgreSQL 16 on a Linux host. It
does not require Vercel, Neon, an AI endpoint, or paid email. Use test data
and keep the pilot private while the Terms and Privacy pages have placeholders.

## Keep Ubuntu running on Windows

Install Ubuntu 24.04 on [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install).
In Ubuntu, add this section to `/etc/wsl.conf` (keep existing settings):

```ini
[boot]
systemd=true
```

Run `wsl --shutdown` in PowerShell and reopen Ubuntu. Check that
`systemctl status` can reach systemd. In Windows Task Scheduler, create a
task **At log on** for the Windows account that owns Ubuntu:

- Program: `wsl.exe`
- Arguments: `-d Ubuntu --exec /bin/sleep infinity` (use the name from `wsl -l -q`).
- Turn off the task's time limit. Set Windows not to sleep or hibernate
  while plugged in.

The foreground process keeps WSL running; systemd services alone do not.
After a reboot Precog comes back when that Windows account signs in.

## Build and migrate

On fresh Ubuntu 24.04 with systemd running, bootstrap installs the packages,
checks out the chosen ref, builds Precog, and starts it on
`http://localhost:8080`. Rerunning keeps the existing database and settings.
See the manual setup below for the individual steps. Bootstrap does not
create a Cloudflare account or tunnel.

Download `deploy/self-host/bootstrap-wsl.sh` from the public Precog repo
at the revision you intend to install, review it, and run
`sudo bash bootstrap-wsl.sh BRANCH_TAG_OR_COMMIT` in Ubuntu.

### Manual setup

Install Node 22 at `/usr/bin/node`, PostgreSQL 16 and its client tools, and
curl in Ubuntu. Create a non-superuser Postgres login that owns a database
named `precog`; keep Postgres on loopback. Place the checkout and build output
at `/opt/precog` on Ubuntu's Linux filesystem. Keep the checkout writable
only by the deploy operator; the service user needs only read access.

Create `/etc/precog` and `/etc/precog/precog.env` as root; keep the file at
mode `0600` until the installer grants the service group read access. Use
literal `NAME=value` lines, not shell commands. Set these values:

| Key                  | Value                                                                                                             |
| -------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`       | A PostgreSQL URL for the local database and its dedicated login. URL-encode the password.                         |
| `BETTER_AUTH_SECRET` | A persistent random secret. Generate it with `openssl rand -hex 32`.                                              |
| `BETTER_AUTH_URL`    | The exact browser origin, for example `http://localhost:8080` on the host or the HTTPS origin of a private proxy. |
| `CRON_SECRET`        | A different random secret, generated with `openssl rand -hex 32`.                                                 |

Keep sign-in enabled and use email/password for the pilot. Without Resend,
Precog does not confirm addresses or send password reset emails. Keep the
listener private: use the host browser or local forwarding; for remote users,
put a TLS reverse proxy with an access gate in front of it. Set
`TRUST_FORWARDED_HOST=1` only when the proxy replaces the forwarded host and
protocol, and set `TRUSTED_CLIENT_IP_HEADER` only to a header the proxy replaces.
Neither is needed to set a fixed origin with `BETTER_AUTH_URL`.

From `/opt/precog`:

```sh
npm ci
PRECOG_BUILD_TARGET=node-server npm run build
sudo bash deploy/self-host/install.sh
```

The default build still targets Vercel. The private Node build leaves
`VERCEL_ENV` unset, so it permits the existing legal placeholders and skips
the automatic migration. The installer creates the service user and private
backup directory, runs the migrations, and installs and starts the units.
Rerun it after a rebuild or configuration change.
Before public launch, replace the placeholders and set `SUPPORT_EMAIL` in the
build environment. Set the real HTTPS `BETTER_AUTH_URL`. Run the explicit
migration with `VERCEL_ENV=production` to apply the same launch checks as on
Vercel, and set that variable for the running service to enforce its
production database checks. Do not use the in-memory database for a pilot
where data must survive restarts.

## Start Precog and the weekly digest

The service listens on `127.0.0.1:8080`. Check it after installation:

```sh
curl --fail http://127.0.0.1:8080/api/health
systemctl list-timers precog-digest.timer
```

The timer calls the loopback digest route every Monday at 13:00 UTC with the
configured bearer secret. It catches up once after downtime. Check
`journalctl -u precog-digest.service` for failed runs and for responses that
report `partial: true`. To run it on demand, use
`sudo systemctl start precog-digest.service`.

## Let two people sign in from anywhere

Use a domain on Cloudflare DNS, such as a Cloudflare-registered domain.
The [Zero Trust Free plan](https://www.cloudflare.com/plans/zero-trust-services/)
covers this access setup; a new domain registration is a separate annual cost.
No router port forwarding is needed.

1. In Cloudflare Zero Trust, enable [One-time PIN](https://developers.cloudflare.com/cloudflare-one/identity/one-time-pin/)
   as the login method. Before routing traffic, create a **Self-hosted**
   Access application for `precog.example.com` covering all paths. Add one
   **Allow** policy with **Include → Emails** set to exactly
   `your-email@example.com` and `spouse-email@example.com`. Select only
   One-time PIN for this application. Do not add a bypass or allow everyone.
2. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/)
   (2025.4.0 or later) at `/usr/bin/cloudflared` in Ubuntu. Create a remotely managed tunnel and
   map `precog.example.com` to `http://127.0.0.1:8080`. Enable **Protect with
   Access** for the route and select the Access application. Save the tunnel
   token as the only line in `/etc/precog/tunnel.token` (root-owned, mode
   `0600`). Do not paste it into a command or share it.
3. Set `BETTER_AUTH_URL=https://precog.example.com` in the service settings
   and rerun the installer. It enables the tunnel service when the token
   file exists. From a private browser on a different network, check that
   an unlisted email cannot enter. Each allowed email uses the PIN gate,
   then signs into its own Precog account. The PIN gate does not give the
   two accounts access to each other's businesses.

## Back up and restore

Use the PostgreSQL 16 client tools. Run the backup with the same database
settings and service user as Precog:

```sh
sudo systemd-run --wait --pipe --collect --uid=precog \
  --property=EnvironmentFile=/etc/precog/precog.env \
  /bin/bash /opt/precog/deploy/self-host/backup.sh \
  "/var/lib/precog-backups/precog-$(date -u +%FT%H%M%SZ).dump"
```

The script uses `pg_dump` custom format and never replaces an existing file.
Dumps contain private business and account data. Keep an encrypted copy off
the server and test restores; a dump on the same disk alone cannot recover
from a disk failure. Separately keep the deployment settings and signing
secret in a secure location. The dump does not include PostgreSQL roles.

Create a **new empty database** (for example `precog_restore`) owned by the
Precog login, as a database administrator. Set `PGHOST`, `PGPORT` and
`PGUSER` for that database, and use a private PostgreSQL password file
(`~/.pgpass` or `PGPASSFILE`, mode `0600`). Restore as the Precog login:

```sh
pg_restore --dbname=precog_restore --no-password --exit-on-error \
  --single-transaction --no-owner --no-privileges /path/to/precog.dump
```

Point a private Precog instance at the restored database and check
`/api/health`, sign in, and reopen a known business. For a real cutover,
stop writers, switch `DATABASE_URL` in the service environment, run any
pending migrations, then start Precog and verify the data before retiring
the old database.
