# Herald Fold browser companion (macOS)

This companion serves a small, authenticated browser view over your private LAN and controls a **dedicated isolated Google Chrome profile** over loopback CDP. It does not touch the normal Chrome profile. Chrome is launched only by the explicit `start` command.

## Install and run

Requires macOS, Python 3.9+, Google Chrome, and a trusted private network for LAN mode.

```sh
cd companion
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m herald_companion.server start
python -m herald_companion.server serve --host 0.0.0.0
```

The server prints a pairing URL containing a random token in the URL fragment. Open that URL on Herald or another device on the trusted LAN. The fragment is not sent in HTTP requests or access logs; the UI stores it only in memory and sends it in `Authorization: Bearer …`. The token is stored at `~/.herald-fold/companion.token` with owner-only permissions. To print the link token again, stop the server and run `python -m herald_companion.server token`; copy it into `http://MAC-LAN-IP:4318/#token=TOKEN`.

To stop the UI server, press Ctrl+C in its terminal. Stop the isolated Chrome window normally. If port 9222 is already occupied, the start command refuses to attach to it automatically; close the dedicated Chrome window before relaunching, or use `serve` directly when reconnecting to a Chrome instance you trust. The CDP port is loopback-only (`127.0.0.1:9222`), and this service will reject a Chrome-discovered WebSocket unless it resolves to loopback on that exact port. Do not expose port 9222 to the LAN. The companion binds to `127.0.0.1` by default; `--host 0.0.0.0` opts into LAN access. The UI has no wildcard CORS policy and no shell execution endpoint.

## Hermes connection

Hermes documents `browser.cdp_url` as a persistent CDP endpoint for attaching to an existing Chromium/Chrome browser (`hermes_cli/config_defaults.py`, browser defaults). Set it in the Hermes config:

```yaml
browser:
  cdp_url: "http://127.0.0.1:9222"
```

On the Mac host, Hermes can connect to the isolated Chrome instance at that URL. The companion's preview and Hermes then operate on the same tabs. The companion UI screenshot is polled about once per second; it is not a video stream. Pause the Hermes agent before manual input. The companion cannot enforce or guarantee that the agent is idle, so concurrent manual input may conflict with agent actions.

## Flight research prompt

Use a prompt such as: “Research flights for my dates and airports. Compare schedules, total prices, baggage, and change rules. Ask me before purchasing or submitting any payment.” The companion only provides browser visibility and input; it does not authorize purchases.

## Scope

The first version offers preview, address navigation, tab selection/open/close, click, basic keys, text entry, and scrolling. It restricts navigation to `http` and `https`. The preview stays on the selected tab; choose another tab in the picker to follow it. CDP does not expose a dependable active-tab signal to this companion. This is a trusted-LAN convenience service, not an internet-facing remote browser product. Keep the pairing token private and use a trusted network. No automated purchase flow is included.
