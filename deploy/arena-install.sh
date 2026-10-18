#!/bin/sh
# Install or update the Arena server on the Pi. Re-runnable. Run as a sudo-capable user:
#   sh deploy/arena-install.sh /tmp/arena-release.tar.gz
# Build the tarball from COMMITTED code (see docs/ARENA.md section 8). It never touches Torch or its data.
#
# Network: the server listens on 127.0.0.1:8770 only. The one way in is a TAILNET-ONLY https port from
# `tailscale serve` (8470). Never Funnel: the Pi's Funnel ports (443, 8443, 10000) belong to other apps, and Arena
# is for friends on your tailnet while testing. Adding the serve handler is the only change to Tailscale's config.
set -eu
TARBALL="$1"
PORT_LOCAL=8770
PORT_TAILNET=8470

id arena >/dev/null 2>&1 || sudo useradd --system --home /var/lib/arena --shell /usr/sbin/nologin arena
sudo mkdir -p /opt/arena /var/lib/arena
sudo chown arena:arena /var/lib/arena && sudo chmod 700 /var/lib/arena

# code: replace everything except the virtual environment
sudo find /opt/arena -mindepth 1 -maxdepth 1 ! -name .venv -exec rm -rf {} +
sudo tar -xzf "$TARBALL" -C /opt/arena
sudo chown -R root:root /opt/arena

[ -x /opt/arena/.venv/bin/python ] || sudo python3 -m venv /opt/arena/.venv
sudo /opt/arena/.venv/bin/pip install -q --disable-pip-version-check -r /opt/arena/arena/requirements.txt

sudo install -m 644 /opt/arena/deploy/arena.service /etc/systemd/system/arena.service
sudo systemctl daemon-reload
sudo systemctl enable arena.service >/dev/null
sudo systemctl restart arena.service
sleep 5
systemctl is-active arena.service

# tailnet-only https -> loopback. --bg keeps it across reboots. Only this one port is added.
if ! sudo tailscale serve status 2>/dev/null | grep -q ":$PORT_TAILNET (tailnet only)"; then
  sudo tailscale serve --bg --https=$PORT_TAILNET "http://127.0.0.1:$PORT_LOCAL"
fi
sudo tailscale serve status 2>/dev/null | grep -A1 ":$PORT_TAILNET"
sudo journalctl -u arena.service -n 8 --no-pager -o cat
