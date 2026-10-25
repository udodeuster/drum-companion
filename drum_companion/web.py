from __future__ import annotations

import hmac
import ipaddress
from io import BytesIO
import json
import secrets
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

import qrcode
from qrcode.image.svg import SvgPathImage

from drum_companion.audio.input import list_input_devices
from drum_companion.audio.output import list_output_devices
from drum_companion.control import DeviceRestartRequired, LiveAudioController, LiveControlError
from drum_companion.groove_library import GrooveLibraryError


class ControlHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, controller: LiveAudioController, pairing_pin: str) -> None:
        super().__init__(address, ControlRequestHandler)
        self.controller = controller
        self.pairing_pin = pairing_pin
        self.phone_url = ""
        self.pairing_used = False
        self.pairing_attempts = 0
        self.sessions: set[str] = set()
        self.pairing_lock = Lock()

    def invalidate_sessions(self) -> None:
        with self.pairing_lock:
            self.sessions.clear()

    def server_close(self) -> None:
        self.invalidate_sessions()
        super().server_close()


class ControlRequestHandler(BaseHTTPRequestHandler):
    server: ControlHTTPServer

    def do_GET(self) -> None:
        if not self._private_client():
            self._send_json(403, {"error": "Only private-network clients are allowed"})
            return
        path = urlsplit(self.path).path
        if path == "/":
            self._serve_page()
        elif path in {"/api/pairing", "/api/pairing-qr.svg"}:
            if not self._loopback_client():
                self._send_json(403, {"error": "Pairing details are only available on the host computer"})
            elif path == "/api/pairing":
                self._send_json(200, {"pin": self.server.pairing_pin, "url": self.server.phone_url})
            else:
                self._send_pairing_qr()
        elif path == "/api/status":
            if self._require_session():
                self._send_json(200, self.server.controller.snapshot())
        elif path == "/api/grooves":
            if self._require_session():
                try:
                    self._send_json(200, {"grooves": self.server.controller.list_saved_grooves()})
                except GrooveLibraryError as exc:
                    self._send_json(500, {"error": str(exc)})
        elif path == "/api/grooves/auto":
            if self._require_session():
                self._send_json(
                    200,
                    {"pattern": self.server.controller.automatic_groove_pattern()},
                )
        elif path == "/api/devices":
            if self._require_session():
                self._send_json(
                    200,
                    {
                        "inputs": [asdict(item) for item in list_input_devices()],
                        "outputs": [asdict(item) for item in list_output_devices()],
                    },
                )
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if not self._private_client():
            self._discard_request_body()
            self.close_connection = True
            self._send_json(403, {"error": "Only private-network clients are allowed"})
            return
        path = urlsplit(self.path).path
        if not self._check_origin():
            self._discard_request_body()
            self.close_connection = True
            self._send_json(403, {"error": "Cross-origin request rejected"})
            return
        if path != "/api/pair" and not self._require_session():
            return
        payload = self._read_json()
        if payload is None:
            return

        if path == "/api/pair":
            self._pair(payload)
            return
        try:
            if path == "/api/start":
                self.server.controller.start()
                self._send_json(202, self.server.controller.snapshot())
            elif path == "/api/stop":
                self.server.controller.stop()
                self._send_json(200, self.server.controller.snapshot())
            elif path == "/api/grooves":
                groove = self.server.controller.save_saved_groove(payload)
                self._send_json(200, {"groove": groove})
            elif path == "/api/preview/start":
                self._send_json(
                    202,
                    self.server.controller.start_preview(payload),
                )
            elif path == "/api/preview/stop":
                self._send_json(
                    200,
                    self.server.controller.stop_preview(),
                )
            else:
                self._send_json(404, {"error": "Not found"})
        except GrooveLibraryError as exc:
            self._send_json(500, {"error": str(exc)})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except LiveControlError as exc:
            self._send_json(409, {"error": str(exc)})

    def do_PATCH(self) -> None:
        if not self._private_client():
            self._discard_request_body()
            self.close_connection = True
            self._send_json(403, {"error": "Only private-network clients are allowed"})
            return
        path = urlsplit(self.path).path
        if path not in {"/api/settings", "/api/preview"}:
            self._discard_request_body()
            self.close_connection = True
            self._send_json(404, {"error": "Not found"})
            return
        if not self._check_origin():
            self._discard_request_body()
            self.close_connection = True
            self._send_json(403, {"error": "Cross-origin request rejected"})
            return
        if not self._require_session():
            return
        payload = self._read_json()
        if payload is None:
            return
        try:
            if path == "/api/preview":
                self._send_json(200, self.server.controller.update_preview(payload))
            else:
                settings = self.server.controller.update_settings(payload)
                self._send_json(200, {"settings": settings})
        except DeviceRestartRequired as exc:
            self._send_json(409, {"error": str(exc), "restart_required": True})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except GrooveLibraryError as exc:
            self._send_json(500, {"error": str(exc)})
        except LiveControlError as exc:
            self._send_json(409, {"error": str(exc)})

    def _pair(self, payload: dict[str, object]) -> None:
        with self.server.pairing_lock:
            if self.server.pairing_used:
                self._send_json(409, {"error": "The pairing PIN has already been used"})
                return
            if self.server.pairing_attempts >= 5:
                self._send_json(429, {"error": "Pairing is locked for this app session"})
                return
            pin = payload.get("pin")
            if not isinstance(pin, str) or not hmac.compare_digest(pin, self.server.pairing_pin):
                self.server.pairing_attempts += 1
                self._send_json(401, {"error": "Invalid pairing PIN"})
                return
            self.server.pairing_used = True
            token = secrets.token_urlsafe(32)
            self.server.sessions.add(token)
        self._send_json(200, {"token": token})

    def _require_session(self) -> bool:
        authorization = self.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token in self.server.sessions:
            return True
        if self.command in {"POST", "PATCH"}:
            self._discard_request_body()
            self.close_connection = True
        self._send_json(401, {"error": "Pair this browser before using controls"})
        return False

    def _discard_request_body(self) -> None:
        length_text = self.headers.get("Content-Length")
        if length_text is None:
            return
        try:
            length = int(length_text)
        except ValueError:
            self.close_connection = True
            return
        if length < 0 or length > 65536:
            self.close_connection = True
            return
        body = self.rfile.read(length)
        if len(body) != length:
            self.close_connection = True

    def _private_client(self) -> bool:
        try:
            address = ipaddress.ip_address(self.client_address[0].split("%", 1)[0])
        except ValueError:
            return False
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return address.is_private or address.is_loopback

    def _loopback_client(self) -> bool:
        try:
            address = ipaddress.ip_address(self.client_address[0].split("%", 1)[0])
        except ValueError:
            return False
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return address.is_loopback

    def _check_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlsplit(origin)
        return parsed.scheme == "http" and parsed.netloc.casefold() == self.headers.get("Host", "").casefold()

    def _read_json(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length"})
            return None
        if length < 0 or length > 65536:
            self._send_json(413, {"error": "Request body is too large"})
            return None
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Request body must be valid JSON"})
            return None
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Request body must be a JSON object"})
            return None
        return payload

    def _serve_page(self) -> None:
        page = Path(__file__).parent / "assets" / "control" / "index.html"
        try:
            content = page.read_bytes()
        except OSError:
            self._send_json(500, {"error": "Control page is unavailable"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._set_security_headers()
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_pairing_qr(self) -> None:
        if not self.server.phone_url:
            self._send_json(503, {"error": "No private-network phone address is available"})
            return
        image = qrcode.make(self.server.phone_url, image_factory=SvgPathImage, border=2)
        content = BytesIO()
        image.save(content)
        svg = content.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self._set_security_headers()
        self.send_header("Content-Length", str(len(svg)))
        self.end_headers()
        self.wfile.write(svg)

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        content = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_security_headers()
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _set_security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self'; "
            "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )

    def log_message(self, format: str, *args: object) -> None:
        return


def create_control_server(
    controller: LiveAudioController,
    pairing_pin: str,
    *,
    host: str = "0.0.0.0",
    port: int = 8765,
    phone_url: str = "",
) -> ControlHTTPServer:
    server = ControlHTTPServer((host, port), controller, pairing_pin)
    server.phone_url = phone_url
    return server