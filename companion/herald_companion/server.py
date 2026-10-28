"""Small authenticated LAN UI for an isolated, loopback-CDP Chrome instance."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import ClientSession, WSMsgType, web

HOME = Path.home() / ".herald-fold"
TOKEN_FILE = HOME / "companion.token"
PROFILE = HOME / "chrome-profile"
CDP_HOST = "127.0.0.1"
CDP_PORT = 9222
MAX_BODY = 64 * 1024


def valid_http_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 4096:
        raise web.HTTPBadRequest(text="URL must be a string under 4096 characters")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise web.HTTPBadRequest(text="Only absolute http:// and https:// URLs are allowed")
    if parsed.username or parsed.password:
        raise web.HTTPBadRequest(text="URLs containing credentials are not allowed")
    return value


def load_or_create_token() -> str:
    HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        token = TOKEN_FILE.read_text(encoding="ascii").strip()
        if len(token) >= 32:
            return token
    except FileNotFoundError:
        pass
    token = secrets.token_urlsafe(32)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(token + "\n")
    return token


def chrome_path() -> str | None:
    candidates = [shutil.which("google-chrome"),
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    return next((x for x in candidates if x and Path(x).is_file()), None)


def lan_address() -> str:
    try:
        addresses = socket.getaddrinfo(socket.gethostname(), None, type=socket.SOCK_STREAM)
        for item in addresses:
            address = item[4][0]
            if not address.startswith(("127.", "::1", "fe80:")):
                return address
    except OSError:
        pass
    return "<MAC-LAN-IP>"


class CDP:
    def __init__(self):
        self.http = f"http://{CDP_HOST}:{CDP_PORT}"
        self.session: ClientSession | None = None
        self.ws = None
        self.reader: asyncio.Task | None = None
        self.pending: dict[int, asyncio.Future] = {}
        self.counter = 0
        self.lock = asyncio.Lock()
        self.operation_lock = asyncio.Lock()
        self.target_id = ""
        self.session_id = ""
        self.last_activity = time.monotonic()

    async def ensure(self):
        if self.session is None:
            self.session = ClientSession()
        if self.ws is not None and not self.ws.closed:
            return
        async with self.session.get(f"{self.http}/json/version") as resp:
            if resp.status != 200:
                raise RuntimeError(f"Chrome CDP discovery returned HTTP {resp.status}")
            info = await resp.json()
        ws_url = info.get("webSocketDebuggerUrl", "")
        p = urlsplit(ws_url)
        try:
            ip = socket.gethostbyname(p.hostname or "")
        except OSError:
            ip = ""
        if p.scheme != "ws" or ip not in {"127.0.0.1", "::1"} or p.port != CDP_PORT:
            raise RuntimeError("Chrome returned a non-loopback or unexpected CDP WebSocket URL")
        self.ws = await self.session.ws_connect(ws_url, heartbeat=20, max_msg_size=16 * 1024 * 1024)
        self.reader = asyncio.create_task(self._read())
        tabs = await self.tabs()
        pages = [t for t in tabs if t.get("type") == "page"]
        if not pages:
            result = await self.call("Target.createTarget", {"url": "about:blank"})
            self.target_id = result["targetId"]
        else:
            self.target_id = pages[0]["id"]
        result = await self.call("Target.attachToTarget", {"targetId": self.target_id, "flatten": True})
        self.session_id = result["sessionId"]

    async def _read(self):
        failure = "Chrome CDP connection closed"
        try:
            async for msg in self.ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                try:
                    data = json.loads(msg.data)
                except ValueError:
                    continue
                future = self.pending.pop(data.get("id"), None)
                if future and not future.done():
                    future.set_result(data)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            failure = f"CDP connection closed: {exc}"
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(RuntimeError(failure))
            self.pending.clear()

    async def call(self, method: str, params: dict | None = None, session_id: str | None = None):
        await self.ensure_socket()
        async with self.lock:
            self.counter += 1
            rid = self.counter
            future = asyncio.get_running_loop().create_future()
            self.pending[rid] = future
            frame = {"id": rid, "method": method, "params": params or {}}
            if session_id:
                frame["sessionId"] = session_id
            try:
                await self.ws.send_json(frame)
                data = await asyncio.wait_for(future, 15)
            except asyncio.TimeoutError:
                raise RuntimeError(f"Chrome timed out responding to {method}. Retry after checking Chrome.") from None
            finally:
                self.pending.pop(rid, None)
            self.last_activity = time.monotonic()
            if "error" in data:
                raise RuntimeError(data["error"].get("message", "CDP command failed"))
            return data.get("result", {})

    async def ensure_socket(self):
        if self.session is None:
            self.session = ClientSession()
        if self.ws is None or self.ws.closed:
            await self.ensure()

    async def tabs(self):
        await self.ensure_http()
        async with self.session.get(f"{self.http}/json/list") as resp:
            if resp.status != 200:
                raise RuntimeError(f"Chrome tab list returned HTTP {resp.status}")
            return await resp.json()

    async def ensure_http(self):
        if self.session is None:
            self.session = ClientSession()

    async def select(self, target: str):
        tabs = await self.tabs()
        if target not in {t.get("id") for t in tabs if t.get("type") == "page"}:
            raise web.HTTPBadRequest(text="Unknown Chrome tab")
        if self.session_id and self.ws and not self.ws.closed:
            try:
                await self.call("Target.detachFromTarget", {"sessionId": self.session_id})
            except Exception:
                pass
        self.target_id = target
        result = await self.call("Target.attachToTarget", {"targetId": target, "flatten": True})
        self.session_id = result["sessionId"]
        await self.call("Target.activateTarget", {"targetId": target})

    async def close(self):
        if self.reader:
            self.reader.cancel()
        if self.ws and not self.ws.closed:
            await self.ws.close()
        if self.session:
            await self.session.close()


CDP_KEY = web.AppKey("cdp", CDP)


TOKEN_KEY = web.AppKey("token", str)


@web.middleware
async def auth_middleware(request, handler):
    if request.path.startswith("/api/"):
        auth = request.headers.get("Authorization", "")
        token = request.app[TOKEN_KEY]
        if not secrets.compare_digest(auth, f"Bearer {token}"):
            raise web.HTTPUnauthorized(text="Invalid or missing companion token")
    return await handler(request)


@web.middleware
async def errors_middleware(request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as exc:
        return web.json_response({"error": f"Chrome companion request failed: {exc}"}, status=502)


async def index(request):
    return web.FileResponse(Path(__file__).with_name("index.html"))


async def health(request):
    return web.json_response({"ok": True})


async def screenshot(request):
    cdp: CDP = request.app[CDP_KEY]
    async with cdp.operation_lock:
        await cdp.ensure()
        target_id = cdp.target_id
        result = await cdp.call("Page.captureScreenshot", {"format": "jpeg", "quality": 68, "captureBeyondViewport": False}, cdp.session_id)
        metrics = await cdp.call("Page.getLayoutMetrics", {}, cdp.session_id)
        viewport = metrics.get("cssVisualViewport") or metrics.get("cssLayoutViewport") or {}
        return web.json_response({"data": result["data"], "target_id": target_id,
                                  "viewport": {"width": viewport.get("clientWidth", 0), "height": viewport.get("clientHeight", 0)},
                                  "at": time.time()})


async def tabs(request):
    rows = await request.app[CDP_KEY].tabs()
    return web.json_response([{"id": t.get("id"), "title": t.get("title", ""), "url": t.get("url", ""), "type": t.get("type")} for t in rows if t.get("type") == "page"])


async def action(request):
    cdp: CDP = request.app[CDP_KEY]
    async with cdp.operation_lock:
        return await _action_locked(request)


async def _action_locked(request):
    cdp: CDP = request.app[CDP_KEY]
    try:
        body = await request.json()
    except (ValueError, UnicodeError):
        raise web.HTTPBadRequest(text="Valid JSON is required") from None
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text="JSON object required")
    op = body.get("op")
    await cdp.ensure()
    expected_target = body.get("target_id")
    if expected_target is not None and expected_target != cdp.target_id:
        raise web.HTTPConflict(text="The preview changed tabs. Wait for it to refresh, then retry.")
    sid = cdp.session_id
    if op == "navigate":
        url = valid_http_url(body.get("url"))
        await cdp.call("Page.navigate", {"url": url}, sid)
    elif op == "select_tab":
        await cdp.select(str(body.get("id", "")))
    elif op == "new_tab":
        url = valid_http_url(body.get("url", "https://www.google.com"))
        r = await cdp.call("Target.createTarget", {"url": url})
        await cdp.select(r["targetId"])
    elif op == "close_tab":
        closed_target = cdp.target_id
        await cdp.call("Target.closeTarget", {"targetId": closed_target})
        # Chrome may list a closing renderer briefly after acknowledging closeTarget.
        cdp.session_id = ""
        pages = [t for t in await cdp.tabs() if t.get("type") == "page" and t.get("id") != closed_target]
        if pages:
            await cdp.select(pages[0]["id"])
        else:
            result = await cdp.call("Target.createTarget", {"url": "about:blank"})
            await cdp.select(result["targetId"])
    elif op == "click":
        x, y = body.get("x"), body.get("y")
        if not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in (x, y)):
            raise web.HTTPBadRequest(text="Invalid click coordinates")
        metrics = await cdp.call("Page.getLayoutMetrics", {}, sid)
        viewport = metrics.get("cssVisualViewport") or metrics.get("cssLayoutViewport") or {}
        x, y = x * viewport.get("clientWidth", 0), y * viewport.get("clientHeight", 0)
        await cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}, sid)
        await cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}, sid)
    elif op == "type":
        value = body.get("text", "")
        if not isinstance(value, str) or len(value) > 10000:
            raise web.HTTPBadRequest(text="Text must be under 10000 characters")
        await cdp.call("Input.insertText", {"text": value}, sid)
    elif op == "key":
        key = body.get("key")
        keys = {"Enter": ("Enter", "Enter", 13), "Backspace": ("Backspace", "Backspace", 8), "Tab": ("Tab", "Tab", 9), "Escape": ("Escape", "Escape", 27), "ArrowUp": ("ArrowUp", "ArrowUp", 38), "ArrowDown": ("ArrowDown", "ArrowDown", 40), "ArrowLeft": ("ArrowLeft", "ArrowLeft", 37), "ArrowRight": ("ArrowRight", "ArrowRight", 39), "Space": (" ", "Space", 32)}
        if key not in keys:
            raise web.HTTPBadRequest(text="Unsupported key")
        name, code, vk = keys[key]
        await cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": name, "code": code, "windowsVirtualKeyCode": vk}, sid)
        await cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": name, "code": code, "windowsVirtualKeyCode": vk}, sid)
    elif op == "scroll":
        x, y, dy = body.get("x", .5), body.get("y", .5), body.get("dy", .4)
        if not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in (x, y)) or not isinstance(dy, (int, float)) or abs(dy) > 1:
            raise web.HTTPBadRequest(text="Invalid scroll values")
        metrics = await cdp.call("Page.getLayoutMetrics", {}, sid)
        viewport = metrics.get("cssVisualViewport") or metrics.get("cssLayoutViewport") or {}
        x, y, dy = x * viewport.get("clientWidth", 0), y * viewport.get("clientHeight", 0), dy * viewport.get("clientHeight", 0)
        await cdp.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": x, "y": y, "deltaY": dy, "deltaX": 0}, sid)
    else:
        raise web.HTTPBadRequest(text="Unsupported operation")
    return web.json_response({"ok": True})


def create_app(token: str | None = None, cdp: CDP | None = None):
    app = web.Application(middlewares=[errors_middleware, auth_middleware], client_max_size=MAX_BODY)
    app[TOKEN_KEY] = token or load_or_create_token()
    app[CDP_KEY] = cdp or CDP()
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/api/screenshot", screenshot)
    app.router.add_get("/api/tabs", tabs)
    app.router.add_post("/api/action", action)
    async def cleanup(application):
        await application[CDP_KEY].close()
    app.on_cleanup.append(cleanup)
    return app


def start_chrome():
    binary = chrome_path()
    if not binary:
        raise SystemExit("Google Chrome not found. Install Google Chrome and retry.")
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex((CDP_HOST, CDP_PORT)) == 0:
            raise SystemExit("Port 9222 is already in use. Close the dedicated Chrome window before starting again, or run 'serve' directly to reconnect to a Chrome instance you trust.")
    PROFILE.mkdir(mode=0o700, parents=True, exist_ok=True)
    args = [binary, f"--remote-debugging-address={CDP_HOST}", f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={PROFILE}", "--no-first-run", "--no-default-browser-check", "about:blank"]
    process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(80):
        with socket.socket() as probe:
            probe.settimeout(.2)
            if probe.connect_ex((CDP_HOST, CDP_PORT)) == 0:
                print(f"Started isolated Google Chrome with profile {PROFILE} and loopback CDP at {CDP_HOST}:{CDP_PORT}.")
                return
        if process.poll() is not None:
            raise SystemExit("Chrome exited before its debugging port became ready. Check the dedicated profile and retry.")
        time.sleep(.1)
    process.terminate()
    raise SystemExit("Chrome did not become ready within 8 seconds. Retry after checking Chrome.")


def main():
    parser = argparse.ArgumentParser(description="Authenticated Herald Fold Chrome companion")
    parser.add_argument("command", choices=("start", "serve", "token"), help="start Chrome, serve UI, or print pairing token")
    parser.add_argument("--host", default="127.0.0.1", help="UI bind address; use 0.0.0.0 for trusted LAN access")
    parser.add_argument("--port", default=4318, type=int)
    args = parser.parse_args()
    token = load_or_create_token()
    if args.command == "start":
        start_chrome()
    elif args.command == "token":
        print(f"Pairing token: {token}")
    else:
        shown_host = lan_address() if args.host == "0.0.0.0" else args.host
        print(f"Herald browser companion: http://{shown_host}:{args.port}/#token={token}")
        if args.host == "0.0.0.0":
            print("LAN mode is active. Open the URL from a trusted private network; keep the pairing token private.")
        web.run_app(create_app(token), host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
