#!/bin/bash
# BlakeGPT droplet first boot. __TS_AUTHKEY__ and __REF__ are filled in at provision time; never commit a filled copy.
set -euo pipefail
exec > /var/log/blakegpt-init.log 2>&1
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
apt-get update && apt-get install -y vnstat python3
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --authkey='__TS_AUTHKEY__' --hostname=blakegpt --ssh
curl -fsSL -o /root/bootstrap.sh "https://raw.githubusercontent.com/CatCorner22/precog/__REF__/deploy/self-host/bootstrap-wsl.sh"
bash /root/bootstrap.sh '__REF__'
origin="https://$(tailscale status --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
sed -i "s#^BETTER_AUTH_URL=.*#BETTER_AUTH_URL=${origin}#" /etc/precog/precog.env
(cd /opt/precog && bash deploy/self-host/install.sh)
tailscale serve --bg --https=443 http://127.0.0.1:8080
cat > /usr/local/bin/blakegpt-egress-cap <<'CAP'
#!/bin/bash
# Stop serving if this month's outbound traffic passes 1,500 GiB (plan includes 2,000 GiB).
tx=$(vnstat --json m 1 | python3 -c 'import json,sys;d=json.load(sys.stdin)["interfaces"];print(sum(i["traffic"]["month"][-1]["tx"] for i in d if i["traffic"]["month"]))')
if [ "${tx:-0}" -gt $((1500*1024*1024*1024)) ]; then tailscale serve reset; systemctl stop precog; logger -t blakegpt "egress cap hit: $tx bytes"; fi
CAP
chmod 755 /usr/local/bin/blakegpt-egress-cap
echo '*/15 * * * * root /usr/local/bin/blakegpt-egress-cap' > /etc/cron.d/blakegpt-egress-cap
echo "BLAKEGPT READY ${origin}"
