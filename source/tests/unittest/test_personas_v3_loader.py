import json
import unittest
from pathlib import Path

from tools.enxame_usuario.migrate_personas_v1_to_v3 import (
    FERNANDA_CANONICAL_SNIPPET,
    LEGACY_PERSONAS_PATH,
    build_v3_payload,
    canonicalize_legacy_dataset,
)
from tools.enxame_usuario.personas_loader import (
    OUTPUT_DURATION_KEY,
    calculate_adjusted_distribution,
    calculate_persona_quotas,
    load_personas_file,
)


ROOT_DIR = Path(__file__).resolve().parents[3]
PERSONAS_V3_PATH = ROOT_DIR / "personas_v3.json"


class TestPersonasV3Loader(unittest.TestCase):
    def test_calculate_adjusted_distribution(self):
        adjusted = calculate_adjusted_distribution(
            {"horario-comercial": 0.72, "noite": 0.28},
            {"horario-comercial": 1.3, "noite": 0.5},
        )
        self.assertAlmostEqual(adjusted["horario-comercial"], 0.8699, places=4)
        self.assertAlmostEqual(adjusted["noite"], 0.1301, places=4)

    def test_calculate_persona_quotas(self):
        quotas = calculate_persona_quotas(
            {"a": 2.0, "b": 1.0, "c": 1.0},
            total_simulations=40,
            minimum_per_persona=5,
        )
        self.assertEqual(quotas, {"a": 20, "b": 10, "c": 10})

    def test_prompt_round_trip_matches_canonical_legacy(self):
        payload = json.loads(PERSONAS_V3_PATH.read_text(encoding="utf-8"))
        canonical_personas, _ = canonicalize_legacy_dataset(LEGACY_PERSONAS_PATH)

        for canonical in canonical_personas:
            persona_payload = payload["personas"][canonical.slug]
            reconstructed = payload["template_prompt"].format(
                identidade=persona_payload["identidade"],
                como_agir=persona_payload["como_agir"],
                missao=persona_payload["missao"],
            )
            self.assertEqual(reconstructed, canonical.canonical_prompt)

    def test_loader_expands_to_v1_contract(self):
        expanded = load_personas_file(str(PERSONAS_V3_PATH))
        self.assertEqual(len(expanded), 300)
        self.assertEqual(list(expanded.keys())[0], "1")
        self.assertEqual(list(expanded.keys())[-1], "300")

        for key, value in expanded.items():
            self.assertTrue(key.isdigit())
            self.assertIsInstance(value["persona"], str)
            self.assertIn(value[OUTPUT_DURATION_KEY], {"rapida", "media", "lenta"})
            self.assertIn(value["offset"], {"horario-comercial", "noite"})
            self.assertIsInstance(value["weekend"], bool)

    def test_loader_is_deterministic(self):
        first = load_personas_file(str(PERSONAS_V3_PATH))
        second = load_personas_file(str(PERSONAS_V3_PATH))
        self.assertEqual(first, second)

    def test_fernanda_canonicalization_is_reported(self):
        payload, audit = build_v3_payload()
        self.assertEqual(len(audit["textual_variants"]), 1)
        anomaly = audit["textual_variants"][0]
        self.assertEqual(anomaly["slug"], "fernanda_costa")
        canonical_variants = [variant for variant in anomaly["variants"] if variant["canonical"]]
        self.assertEqual(len(canonical_variants), 1)
        self.assertIn(FERNANDA_CANONICAL_SNIPPET, canonical_variants[0]["prompt"])
        self.assertEqual(payload["personas"]["fernanda_costa"]["peso_persona"], 2.0)


if __name__ == "__main__":
    unittest.main()
