import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from drum_companion.groove_library import (
    GrooveLibrary,
    GrooveLibraryError,
    INSTRUMENTS,
    SavedGroove,
)


def make_groove(**overrides):
    tracks = {instrument: (False,) * 16 for instrument in INSTRUMENTS}
    levels = {instrument: 0.75 for instrument in INSTRUMENTS}
    values = {"id": "12345678-1234-5678-1234-567812345678", "name": "Verse", "tracks": tracks, "levels": levels}
    values.update(overrides)
    return SavedGroove(**values)


class TestSavedGroove(unittest.TestCase):
    def test_creates_stable_id_and_normalizes_immutable_track_data(self):
        groove = SavedGroove.create(
            "Verse",
            {instrument: [False] * 16 for instrument in INSTRUMENTS},
            {instrument: 0.5 for instrument in INSTRUMENTS},
        )

        self.assertEqual(str(UUID(groove.id)), groove.id)
        self.assertEqual(len(groove.tracks["kick"]), 16)
        with self.assertRaises(TypeError):
            groove.levels["kick"] = 1.0

    def test_rejects_invalid_id_and_empty_or_trimmed_name(self):
        for overrides in (
            {"id": "not-a-uuid"},
            {"id": "12345678123456781234567812345678"},
            {"name": ""},
            {"name": "  "},
            {"name": " Verse "},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                make_groove(**overrides)

    def test_requires_exact_tracks_and_sixteen_boolean_steps(self):
        tracks = {instrument: (False,) * 16 for instrument in INSTRUMENTS}
        with self.assertRaisesRegex(ValueError, "exactly"):
            make_groove(tracks={**tracks, "tom": (False,) * 16})
        with self.assertRaisesRegex(ValueError, "exactly 16"):
            make_groove(tracks={**tracks, "kick": (False,) * 15})
        with self.assertRaisesRegex(ValueError, "booleans"):
            make_groove(tracks={**tracks, "kick": (1,) + (False,) * 15})

    def test_requires_all_track_levels_to_be_finite_and_bounded(self):
        levels = {instrument: 0.75 for instrument in INSTRUMENTS}
        with self.assertRaisesRegex(ValueError, "exactly"):
            make_groove(levels={"kick": 0.5})
        for invalid in (-0.01, 1.01, float("nan"), float("inf"), True):
            with self.subTest(level=invalid), self.assertRaises(ValueError):
                make_groove(levels={**levels, "kick": invalid})


class TestGrooveLibrary(unittest.TestCase):
    def test_explicit_save_persists_versioned_library_across_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grooves.json"
            groove = make_groove()

            self.assertEqual(GrooveLibrary(path).list_grooves(), ())
            self.assertFalse(path.exists())

            GrooveLibrary(path).save_groove(groove)

            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["version"], 1)
            self.assertEqual(GrooveLibrary(path).list_grooves(), (groove,))

    def test_rejects_duplicate_names_case_insensitively_and_updates_same_id(self):
        with tempfile.TemporaryDirectory() as directory:
            library = GrooveLibrary(Path(directory) / "grooves.json")
            first = make_groove()
            library.save_groove(first)

            duplicate = make_groove(
                id="22345678-1234-5678-1234-567812345678",
                name="verse",
            )
            with self.assertRaisesRegex(ValueError, "already exists"):
                library.save_groove(duplicate)

            updated = make_groove(name="Verse", levels={instrument: 0.25 for instrument in INSTRUMENTS})
            self.assertEqual(library.save_groove(updated), (updated,))

    def test_reports_invalid_or_unsupported_library_instead_of_replacing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grooves.json"
            path.write_text('{"version": 2, "grooves": []}', encoding="utf-8")

            with self.assertRaisesRegex(GrooveLibraryError, "Unable to read"):
                GrooveLibrary(path).list_grooves()
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["version"], 2)

    def test_reports_read_and_write_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            parent_file = Path(directory) / "not-a-directory"
            parent_file.write_text("file", encoding="utf-8")
            with self.assertRaisesRegex(GrooveLibraryError, "Unable to read"):
                GrooveLibrary(parent_file / "grooves.json").list_grooves()

            library = GrooveLibrary(Path(directory) / "grooves.json")
            with patch(
                "drum_companion.groove_library.tempfile.NamedTemporaryFile",
                side_effect=OSError("disk unavailable"),
            ):
                with self.assertRaisesRegex(GrooveLibraryError, "Unable to save"):
                    library.save_groove(make_groove())

    def test_failed_atomic_replace_preserves_previous_library(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grooves.json"
            library = GrooveLibrary(path)
            original = make_groove()
            library.save_groove(original)
            replacement = make_groove(name="Changed")

            with patch("drum_companion.groove_library.os.replace", side_effect=OSError("disk error")):
                with self.assertRaisesRegex(GrooveLibraryError, "Unable to save"):
                    library.save_groove(replacement)

            self.assertEqual(GrooveLibrary(path).list_grooves(), (original,))
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
