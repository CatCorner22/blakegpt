#!/bin/bash
# Usage: DIGITALOCEAN_TOKEN=... TAILSCALE_AUTHKEY=... bash provision.sh REF
# Creates ONE s-1vcpu-2gb droplet ($12/mo flat), no backups, no volumes, and a firewall with no public TCP except SSH from this machine.
set -euo pipefail
REF=$1; API=https://api.digitalocean.com/v2; H=(-H "Authorization: Bearer $DIGITALOCEAN_TOKEN" -H 'Content-Type: application/json')
myip=$(curl -fsS https://api.ipify.org)
key_id=$(curl -fsS "${H[@]}" -X POST $API/account/keys -d "$(python3 -c 'import json;print(json.dumps({"name":"devin-blakegpt","public_key":open("/home/ubuntu/.ssh/blakegpt_do.pub").read().strip()}))')" | python3 -c 'import json,sys;print(json.load(sys.stdin)["ssh_key"]["id"])' || curl -fsS "${H[@]}" $API/account/keys | python3 -c 'import json,sys;print([k["id"] for k in json.load(sys.stdin)["ssh_keys"] if k["name"]=="devin-blakegpt"][0])')
userdata=$(sed -e "s#__TS_AUTHKEY__#${TAILSCALE_AUTHKEY}#" -e "s#__REF__#${REF}#g" "$(dirname "$0")/cloud-init.sh")
body=$(USERDATA="$userdata" KEY=$key_id python3 -c 'import json,os;print(json.dumps({"name":"blakegpt","region":"tor1","size":"s-1vcpu-2gb","image":"ubuntu-24-04-x64","backups":False,"ipv6":False,"monitoring":True,"ssh_keys":[int(os.environ["KEY"])],"tags":["blakegpt"],"user_data":os.environ["USERDATA"]}))')
did=$(curl -fsS "${H[@]}" -X POST $API/droplets -d "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin)["droplet"]["id"])')
echo "droplet $did"
fw=$(MYIP=$myip python3 -c 'import json,os;print(json.dumps({"name":"blakegpt-fw","tags":["blakegpt"],"inbound_rules":[{"protocol":"udp","ports":"41641","sources":{"addresses":["0.0.0.0/0","::/0"]}},{"protocol":"tcp","ports":"22","sources":{"addresses":[os.environ["MYIP"]+"/32"]}}],"outbound_rules":[{"protocol":p,"ports":"all" if p!="icmp" else None,"destinations":{"addresses":["0.0.0.0/0","::/0"]}} for p in ("tcp","udp","icmp")]}))' | sed 's/,"ports": null//')
curl -fsS "${H[@]}" -X POST $API/firewalls -d "$fw" | python3 -c 'import json,sys;print("firewall",json.load(sys.stdin)["firewall"]["id"])'
