import json
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf


ASSET_DIRECTORY = Path(__file__).parents[1] / "drum_companion" / "assets" / "drums"


class TestBundledDrumAssets(unittest.TestCase):
    def test_manifest_tracks_cc0_source_for_every_instrument(self):
        manifest = json.loads((ASSET_DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
        assets = manifest["assets"]

        self.assertEqual(manifest["license"], "CC0-1.0")
        self.assertEqual(
            {item["instrument"] for item in assets},
            {"kick", "snare", "closed hi-hat", "open hi-hat", "cymbal"},
        )
        for item in assets:
            self.assertEqual(item["license"], "CC0-1.0")
            self.assertIn("freesound.org/people/", item["source_url"])
            self.assertTrue(item["source_title"])

    def test_every_bundled_preview_decodes_offline(self):
        manifest = json.loads((ASSET_DIRECTORY / "manifest.json").read_text(encoding="utf-8"))

        for item in manifest["assets"]:
            path = ASSET_DIRECTORY / item["file"]
            audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
            self.assertEqual(sample_rate, 44100)
            self.assertGreater(audio.shape[0], 0)
            self.assertEqual(audio.shape[1], 2)
            self.assertTrue(np.isfinite(audio).all())


if __name__ == "__main__":
    unittest.main()