import json
import unittest
from pathlib import Path

from source.simulation_config import validar_seed_config
from source.simulation_config.validation import _dominio_da_variavel, _normalizar_pesos


ROOT = Path(__file__).resolve().parents[3]
V3_PATH = ROOT / "config_v3.json"


class TestValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with V3_PATH.open("r", encoding="utf-8") as arquivo:
            cls.config = json.load(arquivo)
        cls.relatorio = validar_seed_config(cls.config)

    def test_chi2_marginal_persona_id(self):
        resultado = next(
            item for item in self.relatorio["resultados"] if item["variavel"] == "persona_id"
        )
        self.assertTrue(resultado["passou"])
        self.assertGreater(resultado["p_valor"], 0.05)

    def test_chi2_marginal_duracao_offset_weekend(self):
        resultados = [
            item for item in self.relatorio["resultados"] if item["variavel"] != "persona_id"
        ]
        self.assertEqual(len(resultados), 3)
        for resultado in resultados:
            self.assertTrue(resultado["passou"], resultado)
            self.assertGreater(resultado["p_valor"], 0.05)

    def test_garantir_min_por_persona(self):
        self.assertTrue(self.relatorio["min_por_persona_passou"])
        for contagem in self.relatorio["contagem_por_persona"].values():
            self.assertGreaterEqual(contagem, self.relatorio["min_por_persona"])

    def test_normalizar_pesos_rejeita_total_nao_positivo(self):
        with self.assertRaises(ValueError):
            _normalizar_pesos({"a": 0, "b": 0})

    def test_dominio_da_variavel_considera_default(self):
        self.assertEqual(
            _dominio_da_variavel({"depende_de": None, "pesos": {"a": 1, "b": 1}}),
            ["a", "b"],
        )
        self.assertEqual(
            _dominio_da_variavel(
                {
                    "depende_de": "persona_id",
                    "pesos_condicionais": {
                        "ana": {"rapida": 1},
                        "_default": {"media": 1, "lenta": 1},
                    },
                }
            ),
            ["rapida", "media", "lenta"],
        )
