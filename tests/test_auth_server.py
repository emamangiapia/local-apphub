import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from apphub.auth import Auth, initialize_auth
from apphub.manager import AppHubManager
from apphub.server import AppHubServer


class AuthServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        initialize_auth(self.root, "test-password-1234")
        self.server = AppHubServer(("127.0.0.1", 0), AppHubManager(self.root), {"127.0.0.1"})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        hdrs = {"Content-Type": "application/json", **(headers or {})}
        conn.request(method, path, body=None if body is None else json.dumps(body), headers=hdrs)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_password_hash_and_session_cookie(self):
        self.assertTrue(Auth(self.root).verify("test-password-1234"))
        self.assertFalse(Auth(self.root).verify("wrong-password"))
        status, _, _ = self.req("GET", "/api/status")
        self.assertEqual(status, 401)
        status, headers, body = self.req("POST", "/api/login", {"password": "test-password-1234"})
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        csrf = json.loads(body)["csrf"]
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertEqual(self.req("POST", "/api/sync", {}, {"Cookie": cookie})[0], 403)
        self.assertEqual(self.req("POST", "/api/sync", {}, {"Cookie": cookie, "X-AppHub-CSRF": csrf})[0], 202)
        self.assertEqual(self.req("GET", "/api/status", headers={"Cookie": cookie})[0], 200)

    def test_dns_rebinding_protection(self):
        status, _, _ = self.req("GET", "/api/session", headers={"Host": "untrusted.example"})
        self.assertEqual(status, 403)

    def test_static_page_available_before_login(self):
        status, headers, body = self.req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Local AppHub", body)
        self.assertIn(b"/pixel.css", body)
        self.assertIn("Content-Security-Policy", headers)
        code, headers, css = self.req("GET", "/pixel.css")
        self.assertEqual(code, 200)
        self.assertIn(b"Pixel Arcade skin", css)
        self.assertEqual(headers["Content-Type"], "text/css; charset=utf-8")
        code, _, sprite = self.req("GET", "/mascot.svg")
        self.assertEqual(code, 200)
        self.assertIn(b"shape-rendering=\"crispEdges\"", sprite)


class FirstRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.server = AppHubServer(("127.0.0.1", 0), AppHubManager(self.root), {"127.0.0.1"})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        hdrs = {"Content-Type": "application/json", **(headers or {})}
        conn.request(method, path, body=None if body is None else json.dumps(body), headers=hdrs)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_first_run_from_browser_and_gui_app_crud(self):
        _, _, body = self.req("GET", "/api/session")
        self.assertTrue(json.loads(body)["setupRequired"])
        self.assertEqual(self.req("POST", "/api/setup", {"password": "pass123456789", "confirm": "wrong"})[0], 400)
        code, headers, body = self.req("POST", "/api/setup", {
            "password": "pass123456789", "confirm": "pass123456789"})
        self.assertEqual(code, 200)
        self.assertTrue((self.root / "auth.json").exists())
        csrf = json.loads(body)["csrf"]
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        auth = {"Cookie": cookie, "X-AppHub-CSRF": csrf}
        self.assertEqual(self.req("POST", "/api/setup", {
            "password": "password567890", "confirm": "password567890"})[0], 409)
        code, _, _ = self.req("POST", "/api/catalog/apps", {
            "id": "notes", "title": "Note", "repository": "https://github.com/example/notes",
            "branch": "main", "composeFile": "compose.yaml", "autoDeploy": False}, auth)
        self.assertEqual(code, 200)
        code, _, body = self.req("GET", "/api/config", headers=auth)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["apps"][0]["id"], "notes")
        self.assertEqual(self.req("POST", "/api/catalog/apps/notes/remove", {}, auth)[0], 200)
        self.assertEqual(self.req("POST", "/api/catalog/apps", {}, {"Cookie": cookie})[0], 403)

    def test_first_setup_rejects_remote_host(self):
        self.assertEqual(self.req("POST", "/api/setup", {
            "password": "pass123456789", "confirm": "pass123456789"},
            {"Host": "evil.example"})[0], 403)


if __name__ == "__main__":
    unittest.main()
