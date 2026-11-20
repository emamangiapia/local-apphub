"""Local-first, authenticated dashboard and API (Python standard library)."""

from __future__ import annotations

import json
import re
import shutil
import threading
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .auth import Auth, initialize_auth
from .config import ConfigError
from .gitops import OperationError, command
from .manager import AppHubManager


STATIC_ROOT = Path(__file__).resolve().parent / "static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/pixel.css": ("pixel.css", "text/css; charset=utf-8"),
    "/mascot.svg": ("mascot.svg", "image/svg+xml"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
}
ACTION_PATH = re.compile(r"^/api/apps/([a-z][a-z0-9-]{0,39})/(deploy|start|stop)$")
CATALOG_PATH = re.compile(r"^/api/catalog/apps/([a-z][a-z0-9-]{0,39})/(update|remove)$")


class AppHubServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], manager: AppHubManager,
                 allowed_hosts: set[str]):
        super().__init__(address, AppHubHandler)
        self.manager = manager
        self.auth = Auth(manager.root) if (manager.root / "auth.json").exists() else None
        self.setup_lock = threading.Lock()
        self.allowed_hosts = {host.lower() for host in allowed_hosts}


class AppHubHandler(BaseHTTPRequestHandler):
    server: AppHubServer

    def _headers(self, code: int, content_type: str, size: int | None = None,
                 cookie: str | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        if size is not None:
            self.send_header("Content-Length", str(size))
        self.end_headers()

    def _json(self, code: int, payload: dict, cookie: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(code, "application/json; charset=utf-8", len(body), cookie)
        self.wfile.write(body)

    def _path(self) -> str:
        return urlsplit(self.path).path

    def _valid_host(self) -> bool:
        host = self.headers.get("Host", "").lower()
        try:
            host = urlsplit(f"http://{host}").hostname or ""
        except ValueError:
            return False
        return host in self.server.allowed_hosts

    def _session_token(self) -> str | None:
        try:
            parsed = cookies.SimpleCookie()
            parsed.load(self.headers.get("Cookie", ""))
            return parsed["apphub_session"].value if "apphub_session" in parsed else None
        except cookies.CookieError:
            return None

    def _csrf(self) -> str | None:
        return self.server.auth.session(self._session_token()) if self.server.auth else None

    def _local_setup(self) -> bool:
        try:
            hostname = urlsplit("http://" + self.headers.get("Host", "")).hostname
        except ValueError:
            return False
        return (hostname in ("127.0.0.1", "localhost", "::1") and
                self.client_address[0] in ("127.0.0.1", "::1") and
                self.server.server_address[0] in ("127.0.0.1", "localhost", "::1"))

    def _authenticated(self, *, mutating: bool = False) -> bool:
        csrf = self._csrf()
        if not csrf:
            self._json(401, {"error": "Accesso richiesto"})
            return False
        if mutating and self.headers.get("X-AppHub-CSRF") != csrf:
            self._json(403, {"error": "Token di sicurezza non valido"})
            return False
        return True

    def _read_body(self) -> dict | None:
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self._json(415, {"error": "Richiesto application/json"})
            return None
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 <= length <= 4096:
                raise ValueError
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError
            return body
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "JSON non valido"})
            return None

    def _cookie(self, token: str, *, clear: bool = False) -> str:
        parts = [f"apphub_session={token}", "HttpOnly", "SameSite=Strict", "Path=/"]
        if clear:
            parts.append("Max-Age=0")
        else:
            parts.append("Max-Age=86400")
        # HTTPS reverse proxies may set X-Forwarded-Proto; Secure blocks HTTP.
        if self.headers.get("X-Forwarded-Proto", "").lower() == "https":
            parts.append("Secure")
        return "; ".join(parts)

    def do_GET(self) -> None:
        if not self._valid_host():
            self._json(403, {"error": "Host non autorizzato"})
            return
        path = self._path()
        if path in STATIC_FILES:
            name, mime = STATIC_FILES[path]
            data = (STATIC_ROOT / name).read_bytes()
            self._headers(200, mime, len(data))
            self.wfile.write(data)
        elif path == "/api/session":
            csrf = self._csrf()
            self._json(200, {"authenticated": bool(csrf), "csrf": csrf,
                             "setupRequired": self.server.auth is None})
        elif path == "/api/status":
            if self._authenticated():
                self._json(200, self.server.manager.snapshot())
        elif path == "/api/config":
            if self._authenticated():
                self._json(200, self.server.manager.catalog())
        elif path == "/api/diagnostics":
            if self._authenticated():
                self._json(200, self._diagnostics())
        else:
            self._json(404, {"error": "Pagina non trovata"})

    @staticmethod
    def _diagnostics() -> dict:
        def available(args: list[str]) -> bool:
            try:
                command(args, timeout=5)
                return True
            except OperationError:
                return False
        return {
            "gitAvailable": bool(shutil.which("git")),
            "composeAvailable": available(["docker", "compose", "version"]),
            "containerEngineRunning": available(["docker", "info", "--format", "{{.ServerVersion}}"]),
        }

    def do_POST(self) -> None:
        if not self._valid_host():
            self._json(403, {"error": "Host non autorizzato"})
            return
        path = self._path()
        if path == "/api/setup":
            if not self._local_setup():
                self._json(403, {"error": "La prima configurazione è consentita solo sul PC locale"})
                return
            payload = self._read_body()
            if payload is None:
                return
            with self.server.setup_lock:
                if self.server.auth is not None:
                    self._json(409, {"error": "La configurazione iniziale è già stata completata"})
                    return
                password = payload.get("password")
                if (not isinstance(password, str) or len(password) > 1024 or
                        password != payload.get("confirm")):
                    self._json(400, {"error": "Le password non coincidono"})
                    return
                try:
                    initialize_auth(self.server.manager.root, password)
                    self.server.auth = Auth(self.server.manager.root)
                except (ValueError, RuntimeError) as exc:
                    self._json(400, {"error": str(exc)})
                    return
                token, csrf = self.server.auth.create_session()
                self._json(200, {"authenticated": True, "csrf": csrf}, self._cookie(token))
            return
        if path == "/api/login":
            payload = self._read_body()
            if payload is None:
                return
            password = payload.get("password", "")
            if self.server.auth is None:
                self._json(409, {"error": "Completa prima la configurazione iniziale"})
            elif not self.server.auth.allow_login(self.client_address[0]):
                self._json(429, {"error": "Troppi tentativi. Riprova tra cinque minuti"})
            elif not isinstance(password, str) or len(password) > 1024 or not self.server.auth.verify(password):
                self._json(401, {"error": "Password non valida"})
            else:
                token, csrf = self.server.auth.create_session()
                self._json(200, {"authenticated": True, "csrf": csrf}, self._cookie(token))
            return
        if not self._authenticated(mutating=True):
            return
        payload = self._read_body()
        if payload is None:
            return
        if path == "/api/logout":
            self.server.auth.logout(self._session_token())
            self._json(200, {"ok": True}, self._cookie("", clear=True))
        elif path == "/api/sync":
            threading.Thread(target=self.server.manager.sync_once, daemon=True).start()
            self._json(202, {"accepted": True})
        elif path == "/api/settings":
            try:
                settings = self.server.manager.update_settings(payload)
                self._json(200, {"settings": settings})
                threading.Thread(target=self.server.manager.sync_once, daemon=True).start()
            except (ConfigError, OSError) as exc:
                self._json(400, {"error": str(exc)})
        elif path == "/api/catalog/apps":
            try:
                apps = self.server.manager.edit_catalog("add", payload)
                self._json(200, {"apps": apps})
                threading.Thread(target=self.server.manager.sync_once, daemon=True).start()
            except (ConfigError, OperationError, OSError) as exc:
                self._json(400, {"error": str(exc)})
        elif catalog_match := CATALOG_PATH.fullmatch(path):
            slug, operation = catalog_match.groups()
            try:
                apps = self.server.manager.edit_catalog(operation, payload, slug)
                self._json(200, {"apps": apps})
                threading.Thread(target=self.server.manager.sync_once, daemon=True).start()
            except (ConfigError, OperationError, OSError) as exc:
                self._json(400, {"error": str(exc)})
        elif match := ACTION_PATH.fullmatch(path):
            slug, action = match.groups()
            if slug not in {app["id"] for app in self.server.manager.snapshot()["apps"]}:
                self._json(404, {"error": "App non trovata"})
                return
            threading.Thread(target=self.server.manager.action, args=(slug, action), daemon=True).start()
            self._json(202, {"accepted": True})
        else:
            self._json(404, {"error": "Azione non trovata"})

    def do_OPTIONS(self) -> None:
        self._json(403, {"error": "Accesso da altri siti non consentito"})


def serve(manager: AppHubManager, *, host: str = "127.0.0.1", port: int = 8766,
          allowed_hosts: set[str] | None = None) -> None:
    hosts = {"localhost", "127.0.0.1", "::1"} | (allowed_hosts or set())
    if host not in ("127.0.0.1", "localhost", "::1"):
        hosts.add(host)
    if not (manager.root / "auth.json").exists() and host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("Prima configurazione consentita solo su localhost")
    with AppHubServer((host, port), manager, hosts) as server:
        print(f"Local AppHub in ascolto su http://{host}:{port}", flush=True)
        threading.Thread(target=manager.sync_once, daemon=True).start()
        stop = threading.Event()

        def watcher() -> None:
            while not stop.wait(manager.settings["syncIntervalSeconds"]):
                manager.sync_once()

        threading.Thread(target=watcher, daemon=True).start()
        try:
            server.serve_forever(poll_interval=0.5)
        finally:
            stop.set()
