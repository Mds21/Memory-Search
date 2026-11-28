#!/usr/bin/env bash
# Runs ON the server (Ubuntu on Oracle Cloud), called by deploy.ps1. Safe to run again for updates.
#   setup-server.sh <api-host> <allowed-origins>
set -euo pipefail
API_HOST="$1"
ALLOWED_ORIGINS="$2"
APP="$HOME/memory-search"
cd "$APP"

# 1. Docker (Ubuntu packages)
if ! command -v docker >/dev/null || ! sudo docker compose version >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y docker.io docker-compose-v2 || sudo apt-get install -y docker.io docker-compose-plugin
  sudo systemctl enable --now docker
fi

# 2. Oracle's Ubuntu images block everything except SSH in the server's own firewall: open web ports (and keep them open)
for port in 80 443; do
  sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 -p tcp --dport "$port" -j ACCEPT
done
if command -v netfilter-persistent >/dev/null; then sudo netfilter-persistent save; fi

# 3. Settings for docker compose
printf 'API_HOST=%s\nALLOWED_ORIGINS=%s\n' "$API_HOST" "$ALLOWED_ORIGINS" > .env
chmod 600 backend.env .env
mkdir -p data

# 4. The library: only on first install (never overwrite the server's own data on later updates)
if [ -f "$HOME/ms-data.tgz" ]; then
  if [ ! -f data/smriti.db ]; then
    tar -xzf "$HOME/ms-data.tgz" -C data
    echo "library copied to the server"
  else
    echo "the server already has a library; kept it (the laptop copy was not applied)"
  fi
  rm -f "$HOME/ms-data.tgz"
fi

# 5. Build and start (restarts automatically after reboots and crashes)
sudo docker compose up -d --build
sudo docker image prune -f >/dev/null
echo "started; https://$API_HOST will answer once the image model has loaded (first start: a few minutes)"
