import asyncio
import unittest

from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web

from herald_companion.server import create_app, valid_http_url


class FakeCDP:
    def __init__(self):
        self.target_id = "tab-1"
        self.session_id = "session-1"
        self.calls = []
        self.operation_lock = asyncio.Lock()

    async def ensure(self):
        return None

    async def call(self, method, params=None, session_id=None):
        self.calls.append((method, params, session_id))
        if method == "Page.captureScreenshot":
            return {"data": "ZmFrZQ=="}
        if method == "Page.getLayoutMetrics":
            return {"cssVisualViewport": {"clientWidth": 1000, "clientHeight": 700}}
        return {"targetId": "new-tab"}

    async def tabs(self):
        return [{"id": "tab-1", "type": "page", "title": "Example", "url": "https://example.com"}]

    async def select(self, target):
        if target != "tab-1":
            raise web.HTTPBadRequest(text="Unknown Chrome tab")

    async def close(self):
        return None


class CompanionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fake = FakeCDP()
        self.client = TestClient(TestServer(create_app("test-token-123456789012345678901234", self.fake)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_api_requires_bearer_auth(self):
        response = await self.client.get("/api/tabs")
        self.assertEqual(response.status, 401)
        good = await self.client.get("/api/tabs", headers={"Authorization": "Bearer test-token-123456789012345678901234"})
        self.assertEqual(good.status, 200)

    async def test_screenshot_and_click(self):
        headers = {"Authorization": "Bearer test-token-123456789012345678901234"}
        response = await self.client.get("/api/screenshot", headers=headers)
        self.assertEqual((await response.json())["data"], "ZmFrZQ==")
        response = await self.client.post("/api/action", headers=headers, json={"op": "click", "x": .1, "y": .2})
        self.assertEqual(response.status, 200)
        self.assertTrue(any(call[0] == "Input.dispatchMouseEvent" for call in self.fake.calls))

    async def test_invalid_navigation_rejected(self):
        headers = {"Authorization": "Bearer test-token-123456789012345678901234"}
        response = await self.client.post("/api/action", headers=headers, json={"op": "navigate", "url": "file:///etc/passwd"})
        self.assertEqual(response.status, 400)

    async def test_stale_preview_cannot_click_another_tab(self):
        headers = {"Authorization": "Bearer test-token-123456789012345678901234"}
        response = await self.client.post("/api/action", headers=headers,
            json={"op": "click", "target_id": "old-tab", "x": .5, "y": .5})
        self.assertEqual(response.status, 409)
        self.assertFalse(any(call[0] == "Input.dispatchMouseEvent" for call in self.fake.calls))

    async def test_unauthorized_action_never_reaches_chrome(self):
        response = await self.client.post("/api/action", json={"op": "type", "text": "secret"})
        self.assertEqual(response.status, 401)
        self.assertEqual(self.fake.calls, [])

    def test_url_policy(self):
        self.assertEqual(valid_http_url("https://example.com"), "https://example.com")
        for value in ("file:///tmp/x", "javascript:alert(1)", "https://user:pass@example.com"):
            with self.assertRaises(web.HTTPBadRequest):
                valid_http_url(value)


if __name__ == "__main__":
    unittest.main()
