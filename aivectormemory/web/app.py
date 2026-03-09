import os
import sys
import hmac
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote
from aivectormemory.db import ConnectionManager, init_db
from aivectormemory.web.api import handle_api_request
from aivectormemory.log import log

STATIC_DIR = Path(__file__).parent / "static"
PUBLIC_AUTH_ROUTES = {
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
}


class NoFQDNHTTPServer(HTTPServer):
    allow_reuse_address = True

    def server_bind(self):
        import socket
        if self.allow_reuse_address:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()


class WebHandler(SimpleHTTPRequestHandler):
    cm = None
    auth_token = None
    quiet = False

    def address_string(self):
        return self.client_address[0]

    def _check_auth(self):
        if not self.auth_token:
            return True
        provided = (self.headers.get("X-AVM-Server-Token") or "").strip()
        return hmac.compare_digest(provided, self.auth_token)

    def _is_auth_route(self):
        return self.path.split("?")[0].startswith("/api/auth/")

    def _request_path(self):
        return urlparse(self.path).path

    def _extract_session_token(self):
        authz = (self.headers.get("Authorization") or "").strip()
        prefix = "Bearer "
        if not authz.startswith(prefix):
            return None
        token = authz[len(prefix):].strip()
        return token or None

    def _authorize_api_request(self):
        path = self._request_path()
        method = self.command

        if not self._check_auth():
            self.send_error(403, "Forbidden: invalid server token")
            return False

        if (method, path) in PUBLIC_AUTH_ROUTES:
            return True

        from aivectormemory.web.routes.auth import verify_token

        session_token = self._extract_session_token()
        if not session_token:
            self.send_error(401, "Unauthorized: missing bearer token")
            return False

        username = verify_token(session_token)
        if not username:
            self.send_error(401, "Unauthorized: invalid or expired token")
            return False

        self.auth_username = username
        self.auth_session_token = session_token
        return True

    def do_GET(self):
        if self.path.startswith("/api/"):
            if not self._authorize_api_request():
                return
            handle_api_request(self, self.cm)
        else:
            self._serve_static()

    def do_PUT(self):
        if self.path.startswith("/api/"):
            if not self._authorize_api_request():
                return
            handle_api_request(self, self.cm)
        else:
            self.send_error(405)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            if not self._authorize_api_request():
                return
            handle_api_request(self, self.cm)
        else:
            self.send_error(405)

    def do_POST(self):
        if self.path.startswith("/api/"):
            if not self._authorize_api_request():
                return
            handle_api_request(self, self.cm)
        else:
            self.send_error(405)

    def _serve_static(self):
        raw_path = unquote(self.path.split("?", 1)[0])
        rel_path = raw_path.lstrip("/") or "index.html"

        static_root = STATIC_DIR.resolve()
        file_path = (STATIC_DIR / rel_path).resolve()
        if file_path != static_root and static_root not in file_path.parents:
            self.send_error(403, "Forbidden")
            return

        if not file_path.exists() or not file_path.is_file():
            file_path = (STATIC_DIR / "index.html").resolve()
        if not file_path.exists() or (file_path != static_root and static_root not in file_path.parents):
            self.send_error(404)
            return
        content = file_path.read_bytes()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".svg": "image/svg+xml",
        }.get(file_path.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        if self.quiet:
            return
        log.debug("%s", args[0])


def run_web(project_dir: str | None = None, port: int = 9080, bind: str = "127.0.0.1", token: str | None = None, quiet: bool = False, daemon: bool = False):
    cm = ConnectionManager(project_dir=project_dir)
    init_db(cm.conn)

    try:
        from aivectormemory.embedding.engine import EmbeddingEngine
        engine = EmbeddingEngine()
        engine.load()
        cm._embedding_engine = engine
        log.info("Semantic search enabled")
    except Exception as e:
        cm._embedding_engine = None
        log.warning("Semantic search disabled: %s", e)

    WebHandler.cm = cm
    WebHandler.auth_token = token
    WebHandler.quiet = quiet

    server = NoFQDNHTTPServer((bind, port), WebHandler)
    log.info("Web dashboard: http://%s:%d", bind, port)
    if token:
        log.info("Token auth enabled")

    if daemon:
        if not hasattr(os, "fork"):
            log.error("--daemon not supported on Windows")
            sys.exit(1)
        pid = os.fork()
        if pid > 0:
            log.info("Running in background (PID %d)", pid)
            sys.exit(0)
        os.setsid()
        sys.stdin.close()
        devnull = open(os.devnull, "w")
        sys.stdout = devnull
        sys.stderr = devnull

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        cm.close()
        server.server_close()
