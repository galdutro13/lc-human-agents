import copy
import unittest
from pathlib import Path

from tools.enxame_usuario.personas_loader import PersonasLoaderError, validate_v3_payload


ROOT_DIR = Path(__file__).resolve().parents[3]
PERSONAS_V3_PATH = ROOT_DIR / "personas_v3.json"


class TestPersonasV3Schema(unittest.TestCase):
    def setUp(self):
        self.payload = __import__("json").loads(PERSONAS_V3_PATH.read_text(encoding="utf-8"))

    def test_valid_schema_passes(self):
        validated = validate_v3_payload(self.payload)
        self.assertEqual(validated.versao, "3.0")
        self.assertEqual(validated.metodologia.n_simulacoes, 300)
        self.assertEqual(len(validated.personas), 20)

    def test_invalid_distribution_sum_fails(self):
        invalid_payload = copy.deepcopy(self.payload)
        invalid_payload["distribuicao_base"]["duracao"]["rapida"] = 0.5

        with self.assertRaises(PersonasLoaderError):
            validate_v3_payload(invalid_payload)

    def test_missing_template_placeholder_fails(self):
        invalid_payload = copy.deepcopy(self.payload)
        invalid_payload["template_prompt"] = "{identidade} [[como agir]] {como_agir}"

        with self.assertRaises(PersonasLoaderError):
            validate_v3_payload(invalid_payload)

    def test_invalid_adjustment_category_fails(self):
        invalid_payload = copy.deepcopy(self.payload)
        invalid_payload["personas"]["ana_beatriz_silva"]["ajustes"]["offset"]["madrugada"] = 1.2

        with self.assertRaises(PersonasLoaderError):
            validate_v3_payload(invalid_payload)


if __name__ == "__main__":
    unittest.main()
