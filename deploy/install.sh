#!/bin/sh
# Install or update Torch on the Pi. Re-runnable. Run as a sudo-capable user from the unpacked release folder:
#   sh deploy/install.sh /tmp/torch-release.tar.gz /tmp/discord.env
# The second argument (the secrets file) is only needed the first time or to replace the token; it is deleted after.
set -eu
TARBALL="$1"
SECRETS="${2:-}"

id torch >/dev/null 2>&1 || sudo useradd --system --home /var/lib/torch --shell /usr/sbin/nologin torch
sudo mkdir -p /opt/torch /var/lib/torch /etc/torch
sudo chown torch:torch /var/lib/torch && sudo chmod 700 /var/lib/torch
sudo chown root:torch /etc/torch && sudo chmod 750 /etc/torch

# code: replace everything except the virtual environment
sudo find /opt/torch -mindepth 1 -maxdepth 1 ! -name .venv -exec rm -rf {} +
sudo tar -xzf "$TARBALL" -C /opt/torch
sudo chown -R root:root /opt/torch

if [ -n "$SECRETS" ]; then
  sudo install -m 640 -o root -g torch "$SECRETS" /etc/torch/torch.env
  rm -f "$SECRETS"
fi
[ -f /etc/torch/torch.env ] || { echo "no /etc/torch/torch.env: pass the secrets file"; exit 1; }

[ -x /opt/torch/.venv/bin/python ] || sudo python3 -m venv /opt/torch/.venv
sudo /opt/torch/.venv/bin/pip install -q --disable-pip-version-check -r /opt/torch/bot/requirements.txt

sudo install -m 644 /opt/torch/deploy/torch.service /etc/systemd/system/torch.service
sudo systemctl daemon-reload
sudo systemctl enable torch.service >/dev/null
sudo systemctl restart torch.service
sleep 8
systemctl is-active torch.service
sudo journalctl -u torch.service -n 15 --no-pager -o cat
