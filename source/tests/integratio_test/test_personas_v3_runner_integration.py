import os
import unittest
from argparse import Namespace
from datetime import timedelta
from pathlib import Path

import requests

from tools.enxame_usuario.personas_loader import (
    detect_personas_schema_version,
    load_personas_file,
)
from tools.enxame_usuario.start_usuarios import parse_persona_config


ROOT_DIR = Path(__file__).resolve().parents[3]
PERSONAS_V3_PATH = ROOT_DIR / "personas_v3.json"
PERSONAS_V1_PATH = ROOT_DIR / "personas_tf.json"


class TestPersonasV3RunnerIntegration(unittest.TestCase):
    def setUp(self):
        self.default_args = Namespace(
            typing_speed=40.0,
            thinking_min=2.0,
            thinking_max=10.0,
        )

    def test_schema_detection_supports_v1_and_v3(self):
        self.assertEqual(detect_personas_schema_version(str(PERSONAS_V1_PATH)), "v1")
        self.assertEqual(detect_personas_schema_version(str(PERSONAS_V3_PATH)), "v3.0")

    def test_parse_persona_config_accepts_expanded_v3_records(self):
        expanded = load_personas_file(str(PERSONAS_V3_PATH))
        sample = next(iter(expanded.values()))

        prompt, typing_speed, thinking_range, temporal_offset = parse_persona_config(
            sample,
            self.default_args,
        )

        self.assertEqual(prompt, sample["persona"])
        self.assertIsInstance(typing_speed, float)
        self.assertIsInstance(thinking_range, tuple)
        self.assertEqual(len(thinking_range), 2)
        self.assertIsInstance(temporal_offset, timedelta)

    def test_legacy_v1_payload_still_loads(self):
        legacy = load_personas_file(str(PERSONAS_V1_PATH))
        self.assertEqual(len(legacy), 300)
        sample = legacy["1"]
        self.assertIn("persona", sample)
        self.assertIn("offset", sample)
        self.assertIn("weekend", sample)

    @unittest.skipUnless(os.getenv("RUN_PERSONAS_V3_E2E") == "1", "Set RUN_PERSONAS_V3_E2E=1 to run live pipeline smoke test.")
    def test_live_pipeline_smoke(self):
        health = requests.get("http://localhost:8080/health", timeout=5)
        health.raise_for_status()
        expanded = load_personas_file(str(PERSONAS_V3_PATH))
        sample = next(iter(expanded.values()))
        prompt, _, _, _ = parse_persona_config(sample, self.default_args)
        self.assertTrue(prompt.startswith("Você é "))


if __name__ == "__main__":
    unittest.main()
