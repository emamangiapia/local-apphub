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
        self.assertIn("Content-Security-Policy", headers)


if __name__ == "__main__":
    unittest.main()
