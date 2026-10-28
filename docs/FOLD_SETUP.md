# Herald Fold

A foldable Android control plane for an existing Hermes Agent on your Mac. Based on [Giton22/herald](https://github.com/Giton22/herald), with the original license and attribution retained.

## First version

- Unfolded windows at least 720 dp wide: start with full-width chat. Browser tool activity automatically reveals the browser on the right with a 450 ms resize animation. Chat or Activity stays on the left. The browser stays visible between tool calls and after completion, until hidden or the next prompt.
- Use Chat / Activity to choose the left pane and Browser to reveal or hide the right pane. Folding and resizing keep the transcript and remote session mounted.
- Cover screen and narrow split windows: Chat / Browser / Activity tabs, preserving the chat and remote Chrome session while switching.
- Activity shows the same Hermes tool calls, command inputs, outputs and errors as the conversation. Commands go through Hermes and its existing permission/approval system.
- Browser shows the dedicated Mac Chrome page at roughly 300 ms intervals during browser runs, following its visible tab. Controls become read-only while the agent works; manual controls return when the run finishes. Idle previews refresh roughly every 900 ms.
- Existing Herald model/provider settings, sign-in, prompts, approvals and stop controls remain available. No new model billing integration is introduced.

This is a first implementation, not a finished flight booking product. The browser preview is screenshot polling, not video. Manual browser input and agent actions can conflict: press **Stop**, wait for Hermes to finish stopping, then use the browser controls. There is no enforced takeover lock. Follow mode observes Chrome’s visible page without changing its focus. Keep the dedicated browser window open; a hidden tab targeted by Hermes cannot be identified from this preview protocol. If multiple windows are ambiguous, the preview pauses explicitly. Screenshots show page changes, not a mouse cursor. Payment and booking submission require your explicit approval; instruct Hermes accordingly. Device posture, keyboard, and touch behavior still need testing on the actual Oppo Find N5.

## Mac setup

1. Keep your existing Hermes installation and provider sign-in. Enable its browser and terminal toolsets using Hermes's tools settings if needed.
2. From this project run:

   ```sh
   ./companion/start-mac.command
   ```

   This creates an isolated Python environment, launches a separate Google Chrome profile and starts the authenticated companion on your Wi-Fi address, port 4318. It prints a private phone pairing URL. Keep the terminal open.
3. In another terminal configure Hermes to use this Chrome instance, then restart the Hermes dashboard:

   ```sh
   hermes config set browser.cdp_url http://127.0.0.1:9222
   ```

   Continue using the authenticated dashboard address you already connected Herald to (usually port 9119). The companion does not start or change dashboard authentication. Both phone and Mac must be on the same reachable network.
4. Install the fork's APK. It appears as **Herald Fold**, separately from upstream Herald, so sign in to your Hermes dashboard in this app too.
5. Open **Browser → Connect**, paste the complete pairing URL including `#token=...`, and save. It is encrypted at rest using Herald's Android Keystore store and saved separately for each Hermes gateway.
6. In Chat, ask Hermes to use its attached Chrome browser for flight research. Try:

   > Use the connected Chrome browser to research flights. Ask me for missing airports, dates and baggage requirements. Compare schedules, total prices and fare rules. Do not purchase, submit payment or confirm a booking without my explicit approval.

The Chrome CDP port 9222 stays on the Mac's loopback interface. Port 4318 is the authenticated phone view; port 9119 is Hermes. Use the companion only on a trusted private network, or put it behind authenticated HTTPS/Tailscale before broader access. Plain HTTP LAN traffic is not encrypted. Never forward the CDP port publicly.

Stop the companion with Ctrl+C; close the dedicated Chrome window when done. This leaves your ordinary Chrome profile separate. See [companion details](../companion/README.md) for manual commands and protocol scope. The companion provides browser control, while command execution remains in Hermes; it has no shell execution endpoint.

## Build and checks

Upstream requires JDK 25, Android SDK 37 and the provided Gradle wrapper:

```sh
./gradlew :androidApp:assembleDebug :shared:ui:testAndroidHostTest :androidApp:lintDebug
cd companion
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

APK: `androidApp/build/outputs/apk/debug/androidApp-debug.apk`. Debug signing is for local testing. The Wear app is unchanged and is not part of this foldable fork's tested scope.
