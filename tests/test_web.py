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
from drum_companion.control import DeviceRestartRequired, LiveAudioController, LiveControlError
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
        snapshot = self.groove_controller.snapshot()
        snapshot.update({"state": self.state, "running": self.state == "running"})
        return snapshot

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

    def delete_saved_groove(self, groove_id):
        return self.groove_controller.delete_saved_groove(groove_id)

    def automatic_groove_pattern(self):
        return self.groove_controller.automatic_groove_pattern()

    def start_preview(self, values):
        return self.groove_controller.start_preview(values)

    def update_preview(self, values):
        return self.groove_controller.update_preview(values)

    def update_live_groove_draft(self, values):
        return self.groove_controller.update_live_groove_draft(values)

    def stop_preview(self):
        return self.groove_controller.stop_preview()


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
        self.assertIn(b"Welcome to Drum Companion", page)
        self.assertIn(b"private Wi-Fi", page)
        self.assertIn(b"no PIN is needed", page)
        self.assertIn(b"one-time PIN shown on the computer", page)
        self.assertIn(b'<dialog id="welcome-dialog"', page)
        self.assertIn(b'document.querySelector("#welcome-dialog").showModal()', page)
        self.assertIn(b'id="close-welcome"', page)

    def test_control_page_places_audio_devices_in_settings_dialog(self):
        _, _, page = self.request("/")
        text = page.decode("utf-8")
        dialog = text[text.index('<dialog id="settings-dialog"'):text.index("</dialog>", text.index('<dialog id="settings-dialog"'))]

        self.assertIn('id="open-settings"', text)
        self.assertIn('aria-label="Settings"', text)
        for control in ("input-device", "output-device", "drums-enabled", "settings-running-hint"):
            self.assertIn(f'id="{control}"', dialog)
        self.assertEqual(text.count('id="input-device"'), 1)
        self.assertIn("Close Settings and press Stop", dialog)
        self.assertIn('id="pairing-qr"', dialog)
        self.assertIn('id="visible-tracks"', dialog)
        self.assertIn('id="phone-link"', dialog)

    def test_control_page_contains_unique_ids_for_live_controls(self):
        _, _, page = self.request("/")
        parser = ElementIdParser()
        parser.feed(page.decode("utf-8"))

        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertIn(
            b'<label for="groove-select">Playback groove</label><select id="groove-select"><option value="rock">Rock</option><option value="folk">Folk</option><option value="indie">Indie</option></select>',
            page,
        )
        self.assertNotIn(b'id="style"', page)
        self.assertIn(b"const autoStyles = [\"rock\", \"folk\", \"indie\"];", page)
        self.assertIn(b"settings.selected_groove_id || settings.style || \"rock\"", page)
        self.assertIn(b"if (autoStyle) settingsPatch.style = autoStyle;", page)
        self.assertNotIn(b"55% swing", page)
        self.assertNotIn(b"core kick and backbeat remain above zero", page)
        self.assertNotIn(b"three reliable estimates agree", page)
        self.assertIn(b"repeat(16, minmax(30px, 1fr))", page)
        self.assertIn(b"step < 16", page)
        groove_section_start = page.index(b'<section aria-labelledby="groove-heading">')
        groove_section_end = page.index(b"</section>", groove_section_start)
        groove_section = page[groove_section_start:groove_section_end]
        self.assertNotIn(b'class="hint"', groove_section)
        self.assertLess(groove_section_start, page.index(b'id="step-grid-rows"'))
        self.assertLess(page.index(b'id="step-grid-rows"'), groove_section_end)
        self.assertNotIn(b'id="open-groove-editor"', page)
        self.assertNotIn(b'id="editor-target"', page)
        self.assertNotIn(b"Tap a step to toggle it.", page)
        self.assertNotIn(b"Track edits apply to live playback", page)
        self.assertNotIn(b"Preview loops the unsaved draft", page)
        self.assertNotIn(b"Choose a saved groove above to edit it", page)
        self.assertIn(b"const loadSelectedGrooveDraft = async (grooveId)", page)
        self.assertIn(b"return groove;", page)
        self.assertIn(b"setEditorDraft(await selectedGrooveDraft(grooveId), false);", page)
        self.assertIn(b"autoPatternToDraft(pattern)", page)
        self.assertIn(b"await loadSelectedGrooveDraft(status.settings.selected_groove_id);", page)
        self.assertIn(b"if (!settings.selected_groove_id && !editorDirty && status.pattern.length)", page)
        self.assertIn(b'if (editorDirty && !window.confirm("Discard unsaved groove changes?"))', page)
        self.assertIn(b"select.value = previousSelection;", page)
        self.assertIn(b"const draft = await selectedGrooveDraft(grooveId);", page)
        self.assertIn(b"...result.settings", page)
        self.assertIn(b'document.querySelector("#update-groove").addEventListener("click", () => saveDraft(false))', page)
        self.assertIn(b'document.querySelector("#save-groove").addEventListener("click", () => saveDraft(true))', page)
        self.assertIn(b"if (!saveAs) payload.id = editorDraft.id;", page)
        self.assertIn(b"Enter a groove name before saving.", page)
        self.assertIn(b"Automatic-groove snapshots can only be saved as a new groove.", page)
        self.assertIn(b'api("/api/live-groove-draft"', page)
        self.assertIn(b"queueLiveDraftUpdate();", page)
        self.assertIn(b"catch (error) { showMessage(error.message);", page)
        load_grooves_start = page.index(b"const loadGrooves = async")
        load_grooves_end = page.index(b"const blankGroove", load_grooves_start)
        self.assertNotIn(b"setEditorDraft", page[load_grooves_start:load_grooves_end])
        self.assertIn(b"/api/preview/start", page)
        self.assertIn(b"/api/preview/stop", page)
        self.assertIn(b"preview.error", page)
        self.assertIn(b'id="preview-tempo" type="number" min="30" max="300" step="any"', page)
        self.assertIn(b"Number(preview.tempo_bpm).toFixed(1)", page)
        self.assertIn(b"if (!previewTempo.validity.valid)", page)
        self.assertIn(b'preview-status").textContent = error.message', page)
        self.assertIn(b"Preview BPM must be between 30 and 300.", page)
        self.assertNotIn(b'id="phrase"', page)
        self.assertNotIn(b'id="style"', page)
        self.assertNotIn(b'id="onset-timeout-bars"', page)
        self.assertTrue(
            {
                "start", "stop", "tempo", "signal", "confidence", "energy", "pattern",
                "input-device", "output-device", "drums-enabled", "feel",
                "intensity", "master-level", "muted", "lock-tempo", "pairing-qr",
                "display-pin", "phone-link",
                "groove-select", "groove-editor-panel",
                "editor-name", "step-grid-rows", "update-groove", "save-groove", "delete-groove", "editor-status",
                "preview-tempo", "preview-start", "preview-stop", "preview-status",
            }.issubset(parser.ids)
        )
        self.assertIn(b"Preview on host", page)

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

    def test_host_browser_can_create_a_loopback_session_without_consuming_phone_pairing(self):
        status, _, session_body = self.request(
            "/api/host-session",
            method="POST",
            payload={},
        )
        token = json.loads(session_body)["token"]
        api_status, _, api_body = self.request("/api/status", token=token)
        self.assertEqual(status, 200)
        self.assertTrue(token)
        self.assertEqual(api_status, 200)
        self.assertEqual(json.loads(api_body)["state"], "stopped")
        self.assertFalse(self.server.pairing_used)

    def test_host_session_is_denied_to_non_loopback_clients(self):
        with patch.object(ControlRequestHandler, "_loopback_client", return_value=False):
            status, _, body = self.request(
                "/api/host-session",
                method="POST",
                payload={},
            )

        self.assertEqual(status, 403)
        self.assertIn("only available on the host computer", json.loads(body)["error"])
        self.assertEqual(self.server.sessions, {self.token})

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
        self.controller.state = "running"
        auto_before_status, _, auto_before_body = self.request(
            "/api/grooves/auto", authenticated=True
        )
        saved_status, _, saved_body = self.request(
            "/api/grooves", method="POST", payload=payload, authenticated=True
        )
        saved = json.loads(saved_body)["groove"]
        updated_tracks = {**tracks, "snare": [True] + [False] * 15}
        updated_status, _, updated_body = self.request(
            "/api/grooves",
            method="POST",
            payload={**payload, "id": saved["id"], "tracks": updated_tracks},
            authenticated=True,
        )
        copy_status, _, copy_body = self.request(
            "/api/grooves",
            method="POST",
            payload={**payload, "name": "Verse Copy", "tracks": updated_tracks},
            authenticated=True,
        )
        auto_after_status, _, auto_after_body = self.request(
            "/api/grooves/auto", authenticated=True
        )
        live_status, _, live_body = self.request("/api/status", authenticated=True)
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
        empty_name_status, _, empty_name_body = self.request(
            "/api/grooves",
            method="POST",
            payload={**payload, "name": ""},
            authenticated=True,
        )

        self.assertEqual(unpaired_list, 401)
        self.assertEqual(unpaired_save, 401)
        self.assertEqual(json.loads(empty_body)["grooves"], [])
        self.assertEqual(empty_list, 200)
        self.assertEqual(cross_origin, 403)
        self.assertEqual(saved_status, 200)
        self.assertEqual(updated_status, 200)
        updated = json.loads(updated_body)["groove"]
        self.assertEqual(updated["id"], saved["id"])
        self.assertTrue(updated["tracks"]["snare"][0])
        self.assertEqual(copy_status, 200)
        saved_copy = json.loads(copy_body)["groove"]
        self.assertNotEqual(saved_copy["id"], saved["id"])
        self.assertEqual(saved_copy["name"], "Verse Copy")
        self.assertTrue(saved_copy["tracks"]["kick"][0])
        self.assertTrue(saved_copy["tracks"]["snare"][0])
        self.assertEqual(auto_before_status, 200)
        self.assertEqual(auto_after_status, 200)
        self.assertEqual(
            json.loads(auto_after_body)["pattern"],
            json.loads(auto_before_body)["pattern"],
        )
        self.assertEqual(saved["name"], "Verse")
        self.assertEqual(len(saved["tracks"]["kick"]), 16)
        self.assertEqual(live_status, 200)
        self.assertIsNone(json.loads(live_body)["settings"]["selected_groove_id"])
        self.assertEqual(duplicate_status, 400)
        self.assertIn("already exists", json.loads(duplicate_body)["error"])
        self.assertEqual(invalid_status, 400)
        self.assertIn("booleans", json.loads(invalid_body)["error"])
        self.assertEqual(empty_name_status, 400)
        self.assertIn("name must not be empty", json.loads(empty_name_body)["error"])

    def test_shutdown_requires_session_and_stops_server(self):
        unpaired, _, _ = self.request("/api/shutdown", method="POST", payload={})
        cross_origin, _, _ = self.request(
            "/api/shutdown", method="POST", payload={}, authenticated=True, origin="http://attacker.example"
        )
        status, _, body = self.request("/api/shutdown", method="POST", payload={}, authenticated=True)
        self.thread.join(timeout=3.0)

        self.assertEqual(unpaired, 401)
        self.assertEqual(cross_origin, 403)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["shutting_down"])
        self.assertFalse(self.thread.is_alive())

    def test_serves_app_icon_for_browser_and_page_header(self):
        status, content_type, body = self.request("/icon.png")
        favicon_status, favicon_type, _ = self.request("/favicon.ico")
        touch_status, _, _ = self.request("/apple-touch-icon.png")
        _, _, page = self.request("/")

        self.assertEqual((status, content_type), (200, "image/png"))
        self.assertTrue(body.startswith(b"\x89PNG"))
        self.assertEqual((favicon_status, favicon_type), (200, "image/png"))
        self.assertEqual(touch_status, 200)
        self.assertIn(b'rel="icon"', page)
        self.assertIn(b'class="app-logo"', page)

    def test_groove_can_be_renamed_and_deleted_with_auth(self):
        tracks = {instrument: [False] * 16 for instrument in INSTRUMENTS}
        payload = {"name": "Verse", "tracks": tracks, "levels": {i: 1.0 for i in INSTRUMENTS}}
        _, _, body = self.request("/api/grooves", method="POST", payload=payload, authenticated=True)
        saved = json.loads(body)["groove"]
        path = f"/api/grooves/{saved['id']}"

        rename, _, _ = self.request(
            "/api/grooves", method="POST", payload={**payload, "id": saved["id"], "name": "Chorus"}, authenticated=True
        )
        unpaired, _, _ = self.request(path, method="DELETE")
        cross_origin, _, _ = self.request(
            path, method="DELETE", authenticated=True, origin="http://attacker.example"
        )
        deleted, _, deleted_body = self.request(path, method="DELETE", authenticated=True)
        missing, _, _ = self.request(path, method="DELETE", authenticated=True)
        invalid, _, _ = self.request("/api/grooves/not-an-id", method="DELETE", authenticated=True)
        _, _, listed = self.request("/api/grooves", authenticated=True)

        self.assertEqual(rename, 200)
        self.assertEqual(unpaired, 401)
        self.assertEqual(cross_origin, 403)
        self.assertEqual(deleted, 200)
        self.assertIsNone(json.loads(deleted_body)["settings"]["selected_groove_id"])
        self.assertEqual(missing, 404)
        self.assertEqual(invalid, 404)
        self.assertEqual(json.loads(listed)["grooves"], [])

    def test_auto_groove_copy_endpoint_returns_a_sixteen_step_source_grid(self):
        unpaired, _, _ = self.request("/api/grooves/auto")
        status, _, body = self.request("/api/grooves/auto", authenticated=True)

        self.assertEqual(unpaired, 401)
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["pattern"]), 8)

    def test_live_groove_draft_api_applies_unsaved_edits_only_to_selected_target(self):
        tracks = {instrument: [False] * 16 for instrument in INSTRUMENTS}
        tracks["snare"][0] = True
        levels = {instrument: 1.0 for instrument in INSTRUMENTS}
        payload = {
            "selected_groove_id": None,
            "tracks": tracks,
            "levels": levels,
        }

        unpaired, _, _ = self.request(
            "/api/live-groove-draft", method="PATCH", payload=payload
        )
        applied, _, applied_body = self.request(
            "/api/live-groove-draft",
            method="PATCH",
            payload=payload,
            authenticated=True,
        )
        stale, _, stale_body = self.request(
            "/api/live-groove-draft",
            method="PATCH",
            payload={**payload, "selected_groove_id": "22345678-1234-5678-1234-567812345678"},
            authenticated=True,
        )
        invalid, _, invalid_body = self.request(
            "/api/live-groove-draft",
            method="PATCH",
            payload={**payload, "tracks": {**tracks, "kick": [1] * 16}},
            authenticated=True,
        )

        self.assertEqual(unpaired, 401)
        self.assertEqual(applied, 200)
        self.assertTrue(json.loads(applied_body)["updated"])
        self.assertEqual(stale, 409)
        self.assertIn("selected groove changed", json.loads(stale_body)["error"])
        self.assertEqual(invalid, 400)
        self.assertIn("booleans", json.loads(invalid_body)["error"])
        self.assertEqual(self.controller.list_saved_grooves(), [])

    def test_preview_api_requires_pairing_origin_and_routes_preview_lifecycle(self):
        tracks = {instrument: [False] * 16 for instrument in INSTRUMENTS}
        levels = {instrument: 1.0 for instrument in INSTRUMENTS}
        payload = {"tracks": tracks, "levels": levels, "tempo_bpm": 120}
        unpaired, _, _ = self.request(
            "/api/preview/start", method="POST", payload=payload
        )
        cross_origin, _, _ = self.request(
            "/api/preview",
            method="PATCH",
            payload=payload,
            authenticated=True,
            origin="http://attacker.example",
        )
        with (
            patch.object(
                self.controller.groove_controller,
                "start_preview",
                return_value={"preview": {"state": "starting"}},
            ) as start_preview,
            patch.object(
                self.controller.groove_controller,
                "update_preview",
                return_value={"preview": {"state": "running"}},
            ) as update_preview,
            patch.object(
                self.controller.groove_controller,
                "stop_preview",
                return_value={"preview": {"state": "stopped"}},
            ) as stop_preview,
        ):
            started, _, start_body = self.request(
                "/api/preview/start",
                method="POST",
                payload=payload,
                authenticated=True,
            )
            updated, _, update_body = self.request(
                "/api/preview",
                method="PATCH",
                payload=payload,
                authenticated=True,
            )
            stopped, _, stop_body = self.request(
                "/api/preview/stop",
                method="POST",
                payload={},
                authenticated=True,
            )

        self.assertEqual(unpaired, 401)
        self.assertEqual(cross_origin, 403)
        self.assertEqual(started, 202)
        self.assertEqual(json.loads(start_body)["preview"]["state"], "starting")
        self.assertEqual(updated, 200)
        self.assertEqual(json.loads(update_body)["preview"]["state"], "running")
        self.assertEqual(stopped, 200)
        self.assertEqual(json.loads(stop_body)["preview"]["state"], "stopped")
        start_preview.assert_called_once_with(payload)
        update_preview.assert_called_once_with(payload)
        stop_preview.assert_called_once_with()

        with patch.object(
            self.controller.groove_controller,
            "start_preview",
            side_effect=LiveControlError(
                "Stop the live session before starting the groove preview"
            ),
        ):
            blocked, _, blocked_body = self.request(
                "/api/preview/start",
                method="POST",
                payload=payload,
                authenticated=True,
            )
        self.assertEqual(blocked, 409)
        self.assertIn("Stop the live session", json.loads(blocked_body)["error"])

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