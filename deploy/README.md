# Deployment

The live BlakeGPT host is a DigitalOcean Basic `s-1vcpu-2gb` Droplet in
`tor1`, at a flat $12 per month. Its Tailscale hostname is `blakegpt`; Tailscale
Serve provides `https://blakegpt.<tailnet>.ts.net`.

The firewall exposes no public TCP service. It permits UDP `41641` for
Tailscale and SSH on TCP `22` from the admin range only. `vnstat` stops service
when outbound transfer reaches the 1,500 GiB cap.

To update the host, run `bash bootstrap.sh main`.

`digitalocean/cloud-init.sh` and `digitalocean/provision.sh` contain
placeholders for the Tailscale auth key and source ref. Keep filled copies,
SSH keys and API or Tailscale tokens out of this repository.
