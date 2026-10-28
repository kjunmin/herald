#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt

echo "Starting an isolated Google Chrome profile. This does not use your everyday Chrome profile."
.venv/bin/python -m herald_companion.server start

interface="$(route -n get default 2>/dev/null | awk '/interface:/{print $2; exit}')"
lan_ip=""
if [[ -n "$interface" ]]; then
  lan_ip="$(ipconfig getifaddr "$interface" 2>/dev/null || true)"
fi
if [[ -z "$lan_ip" ]]; then
  lan_ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
fi
if [[ -z "$lan_ip" ]]; then
  echo "Could not determine a LAN IPv4 address; pass --host 0.0.0.0 manually after setup."
  exit 1
fi

echo "Pairing link (keep private): http://${lan_ip}:4318/#token=$(.venv/bin/python -m herald_companion.server token | sed 's/^Pairing token: //')"
echo "Hermes config suggestion: browser.cdp_url: http://127.0.0.1:9222"
exec .venv/bin/python -m herald_companion.server serve --host "$lan_ip"
