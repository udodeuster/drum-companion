import json
import threading
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from drum_companion.audio.input import InputDevice
from drum_companion.audio.output import OutputDevice
from drum_companion.control import DeviceRestartRequired, LiveAudioController
from drum_companion.groove_library import GrooveLibrary, GrooveLibraryError, INSTRUMENTS
from drum_companion.web import ControlRequestHandler, create_control_server


class StubController:
    def __init__(self, storage_directory):
        self.state = "stopped"
        self.settings = {}
        self.groove_controller = LiveAudioController(
            groove_library=GrooveLibrary(Path(storage_directory) / "grooves.json")
        )

    def snapshot(self):
        return {"state": self.state, "running": self.state == "running"}

    def start(self):
        self.state = "running"

    def stop(self):
        self.state = "stopped"

    def update_settings(self, values):
        if self.state == "running" and {"input_device", "output_device", "drums_enabled"}.intersection(values):
            raise DeviceRestartRequired("Stop the live session before changing audio devices or drum playback")
        self.settings.update(values)
        return dict(self.settings)

    def list_saved_grooves(self):
        return self.groove_controller.list_saved_grooves()

    def save_saved_groove(self, values):
        return self.groove_controller.save_saved_groove(values)

    def automatic_groove_pattern(self):
        return self.groove_controller.automatic_groove_pattern()


class ElementIdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        self.ids.extend(value for name, value in attrs if name == "id")


class TestControlWebServer(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.controller = StubController(self.storage.name)
        self.server = create_control_server(
            self.controller,
            "123456",
            host="127.0.0.1",
            port=0,
        )
        self.token = "paired-test-session"
        self.server.sessions.add(self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.server.phone_url = f"http://192.168.1.42:{self.server.server_address[1]}/"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=1.0)
        self.server.server_close()
        self.storage.cleanup()

    def request(self, path, *, method="GET", payload=None, authenticated=False, token=None, origin=None):
        headers = {}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated or token is not None:
            headers["Authorization"] = f"Bearer {token or self.token}"
        if origin is not None:
            headers["Origin"] = origin
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=2.0) as response:
                return response.status, response.headers.get_content_type(), response.read()
        except HTTPError as error:
            return error.code, error.headers.get_content_type(), error.read()

    def test_serves_control_page_and_requires_authentication_for_status(self):
        page_status, content_type, page = self.request("/")
        private_status, _, private = self.request("/api/status")
        status, api_type, body = self.request("/api/status", authenticated=True)

        self.assertEqual(page_status, 200)
        self.assertEqual(content_type, "text/html")
        self.assertIn(b"Drum Companion", page)
        self.assertEqual(private_status, 401)
        self.assertEqual(json.loads(private)["error"], "Pair this browser before using controls")
        self.assertEqual(status, 200)
        self.assertEqual(api_type, "application/json")
        self.assertEqual(json.loads(body)["state"], "stopped")

    def test_control_page_contains_unique_ids_for_live_controls(self):
        _, _, page = self.request("/")
        parser = ElementIdParser()
        parser.feed(page.decode("utf-8"))

        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertIn(b"55% swing", page)
        self.assertIn(b"core kick and backbeat remain above zero", page)
        self.assertIn(b"three reliable estimates agree", page)
        self.assertIn(b"repeat(16, minmax(34px, 1fr))", page)
        self.assertIn(b"step < 16", page)
        self.assertIn(b"Copy current Auto groove", page)
        self.assertIn(b"Discard unsaved groove changes?", page)
        self.assertNotIn(b'id="phrase"', page)
        self.assertNotIn(b'id="onset-timeout-bars"', page)
        self.assertTrue(
            {
                "start", "stop", "tempo", "signal", "confidence", "energy", "pattern",
                "input-device", "output-device", "drums-enabled", "style",                 "feel",
                                "intensity", "master-level", "muted", "pairing-qr",
                "display-pin", "phone-link",
                "groove-select", "open-groove-editor", "groove-editor-panel",
                "editor-target", "editor-name", "step-grid-rows", "save-groove", "editor-status",
            }.issubset(parser.ids)
        )

    def test_host_pairing_details_include_fragment_pin_and_svg_qr(self):
        details_status, _, details_body = self.request("/api/pairing")
        qr_status, qr_type, qr_body = self.request("/api/pairing-qr.svg")
        details = json.loads(details_body)

        self.assertEqual(details_status, 200)
        self.assertEqual(details["pin"], "123456")
        self.assertEqual(details["url"], self.server.phone_url)
        self.assertNotIn("#", details["url"])
        self.assertNotIn("123456", details["url"])
        self.assertEqual(qr_status, 200)
        self.assertEqual(qr_type, "image/svg+xml")
        self.assertIn(b"<svg", qr_body)

    def test_pairing_pin_details_are_not_available_to_lan_clients(self):
        from types import SimpleNamespace

        self.assertFalse(
            ControlRequestHandler._loopback_client(
                SimpleNamespace(client_address=("192.168.1.23", 43210))
            )
        )

    def test_playback_lifecycle_and_device_list_are_local_api_routes(self):
        from unittest.mock import patch

        with (
            patch("drum_companion.web.list_input_devices", return_value=[InputDevice(0, "Mic", 1, 48000)]),
            patch("drum_companion.web.list_output_devices", return_value=[OutputDevice(1, "Speakers", 2, 48000)]),
        ):
            started, _, start_body = self.request(
                "/api/start", method="POST", payload={}, authenticated=True
            )
            devices_status, _, devices_body = self.request("/api/devices", authenticated=True)
            stopped, _, stop_body = self.request(
                "/api/stop", method="POST", payload={}, authenticated=True
            )

        self.assertEqual(started, 202)
        self.assertEqual(json.loads(start_body)["state"], "running")
        self.assertEqual(devices_status, 200)
        self.assertEqual(json.loads(devices_body)["inputs"][0]["name"], "Mic")
        self.assertEqual(json.loads(devices_body)["outputs"][0]["name"], "Speakers")
        self.assertEqual(stopped, 200)
        self.assertEqual(json.loads(stop_body)["state"], "stopped")

    def test_settings_api_rejects_unpaired_start_and_reports_restart_requirement(self):
        unpaired, _, _ = self.request("/api/start", method="POST", payload={})
        updated, _, updated_body = self.request(
            "/api/settings",
            method="PATCH",
            payload={"master_level": 0.4, "onset_timeout_bars": 2},
            authenticated=True,
        )
        self.request("/api/start", method="POST", payload={}, authenticated=True)
        restart, _, restart_body = self.request(
            "/api/settings",
            method="PATCH",
            payload={"input_device": 2},
            authenticated=True,
        )

        self.assertEqual(unpaired, 401)
        self.assertEqual(self.controller.state, "running")
        self.assertEqual(updated, 200)
        self.assertEqual(json.loads(updated_body)["settings"]["master_level"], 0.4)
        self.assertEqual(json.loads(updated_body)["settings"]["onset_timeout_bars"], 2)
        self.assertEqual(restart, 409)
        self.assertTrue(json.loads(restart_body)["restart_required"])

    def test_groove_api_requires_pairing_and_saves_validated_grooves(self):
        tracks = {instrument: [False] * 16 for instrument in INSTRUMENTS}
        tracks["kick"][0] = True
        payload = {
            "name": "Verse",
            "tracks": tracks,
            "levels": {instrument: 0.75 for instrument in INSTRUMENTS},
        }

        unpaired_list, _, _ = self.request("/api/grooves")
        unpaired_save, _, _ = self.request(
            "/api/grooves", method="POST", payload=payload
        )
        empty_list, _, empty_body = self.request("/api/grooves", authenticated=True)
        cross_origin, _, _ = self.request(
            "/api/grooves",
            method="POST",
            payload=payload,
            authenticated=True,
            origin="http://attacker.example",
        )
        saved_status, _, saved_body = self.request(
            "/api/grooves", method="POST", payload=payload, authenticated=True
        )
        duplicate_status, _, duplicate_body = self.request(
            "/api/grooves",
            method="POST",
            payload={**payload, "name": "verse"},
            authenticated=True,
        )
        invalid_status, _, invalid_body = self.request(
            "/api/grooves",
            method="POST",
            payload={**payload, "tracks": {**tracks, "kick": [1] * 16}},
            authenticated=True,
        )

        self.assertEqual(unpaired_list, 401)
        self.assertEqual(unpaired_save, 401)
        self.assertEqual(json.loads(empty_body)["grooves"], [])
        self.assertEqual(empty_list, 200)
        self.assertEqual(cross_origin, 403)
        self.assertEqual(saved_status, 200)
        saved = json.loads(saved_body)["groove"]
        self.assertEqual(saved["name"], "Verse")
        self.assertEqual(len(saved["tracks"]["kick"]), 16)
        self.assertEqual(duplicate_status, 400)
        self.assertIn("already exists", json.loads(duplicate_body)["error"])
        self.assertEqual(invalid_status, 400)
        self.assertIn("booleans", json.loads(invalid_body)["error"])

    def test_auto_groove_copy_endpoint_returns_a_sixteen_step_source_grid(self):
        unpaired, _, _ = self.request("/api/grooves/auto")
        status, _, body = self.request("/api/grooves/auto", authenticated=True)

        self.assertEqual(unpaired, 401)
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["pattern"]), 8)

    def test_groove_api_reports_storage_errors(self):
        with patch.object(
            self.controller.groove_controller._groove_library,
            "list_grooves",
            side_effect=GrooveLibraryError("storage unavailable"),
        ):
            list_status, _, list_body = self.request("/api/grooves", authenticated=True)
        tracks = {instrument: [False] * 16 for instrument in INSTRUMENTS}
        payload = {
            "name": "Verse",
            "tracks": tracks,
            "levels": {instrument: 0.75 for instrument in INSTRUMENTS},
        }
        with patch.object(
            self.controller.groove_controller._groove_library,
            "save_groove",
            side_effect=GrooveLibraryError("disk unavailable"),
        ):
            save_status, _, save_body = self.request(
                "/api/grooves",
                method="POST",
                payload=payload,
                authenticated=True,
            )

        self.assertEqual(list_status, 500)
        self.assertIn("storage unavailable", json.loads(list_body)["error"])
        self.assertEqual(save_status, 500)
        self.assertIn("disk unavailable", json.loads(save_body)["error"])

    def test_pairing_pin_is_single_use_and_issues_a_bearer_session(self):
        paired, _, paired_body = self.request(
            "/api/pair", method="POST", payload={"pin": "123456"}
        )
        token = json.loads(paired_body)["token"]
        status, _, status_body = self.request("/api/status", token=token)
        second_pair, _, second_pair_body = self.request(
            "/api/pair", method="POST", payload={"pin": "123456"}
        )
        invalid_token, _, _ = self.request("/api/status", token="not-a-session")

        self.assertEqual(paired, 200)
        self.assertEqual(json.loads(status_body)["state"], "stopped")
        self.assertEqual(second_pair, 409)
        self.assertEqual(json.loads(second_pair_body)["error"], "The pairing PIN has already been used")
        self.assertEqual(invalid_token, 401)

    def test_pairing_rate_limit_and_cross_origin_mutations_are_rejected(self):
        wrong_pins = [
            self.request("/api/pair", method="POST", payload={"pin": "000000"})[0]
            for _ in range(5)
        ]
        locked_out, _, _ = self.request("/api/pair", method="POST", payload={"pin": "123456"})
        cross_origin, _, body = self.request(
            "/api/start",
            method="POST",
            payload={},
            authenticated=True,
            origin="http://attacker.example",
        )

        self.assertEqual(wrong_pins, [401] * 5)
        self.assertEqual(locked_out, 429)
        self.assertEqual(cross_origin, 403)
        self.assertEqual(json.loads(body)["error"], "Cross-origin request rejected")

    def test_app_session_shutdown_invalidates_paired_tokens(self):
        self.server.invalidate_sessions()

        status, _, _ = self.request("/api/status", authenticated=True)

        self.assertEqual(status, 401)
        self.assertFalse(self.server.sessions)


if __name__ == "__main__":
    unittest.main()