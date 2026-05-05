import json
import tempfile
import unittest
from pathlib import Path

from source.simulation_config import ConfigValidationError, carregar_config_v43


ROOT = Path(__file__).resolve().parents[3]
V43_PATH = ROOT / "config_v4_3.json"
LEGACY_V4_PATH = ROOT / "source/tests/fixtures/legacy/config_v4_1.json"
LEGACY_V42_PATH = ROOT / "source/tests/fixtures/legacy/config_v4_2.json"
LEGACY_V3_PATH = ROOT / "source/tests/fixtures/legacy/config_v3.json"
LEGACY_V1_PATH = ROOT / "source/tests/fixtures/legacy/personas_tf.json"


class TestLoaderV43(unittest.TestCase):
    def test_carregar_config_v43_valido(self):
        config = carregar_config_v43(V43_PATH)

        self.assertEqual(config["versao"], "4.3")
        self.assertEqual(config["contexto_negocio"], "cartao_de_credito")
        self.assertEqual(len(config["personas"]), 24)
        self.assertEqual(len(config["missoes"]), 26)

    def test_rejeita_schemas_legados(self):
        for path in (LEGACY_V4_PATH, LEGACY_V42_PATH, LEGACY_V3_PATH, LEGACY_V1_PATH):
            with self.assertRaisesRegex(ConfigValidationError, "Esperado '4.3'"):
                carregar_config_v43(path)

    def test_rejeita_json_estruturalmente_invalido(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8") as tmp:
            json.dump({"versao": "4.3"}, tmp, ensure_ascii=False)
            tmp.flush()
            with self.assertRaisesRegex(ConfigValidationError, "Configuração v4.3 inválida"):
                carregar_config_v43(tmp.name)
