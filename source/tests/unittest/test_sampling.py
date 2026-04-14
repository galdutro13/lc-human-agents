import json
import unittest
from pathlib import Path

import numpy as np

from source.simulation_config import (
    amostrar_categorica,
    gerar_simulacoes,
    montar_prompt,
    obter_pesos,
    parse_prompt_monolitico,
)


ROOT = Path(__file__).resolve().parents[3]
LEGACY_PATH = ROOT / "personas_tf.json"


class TestSampling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with LEGACY_PATH.open("r", encoding="utf-8") as arquivo:
            cls.legacy = json.load(arquivo)

    def test_montar_prompt_reconstroi_prompt_exato(self):
        prompt_original = self.legacy["1"]["persona"]
        partes = parse_prompt_monolitico(prompt_original)

        prompt_reconstruido = montar_prompt(partes, partes["template_prompt"])

        self.assertEqual(
            prompt_reconstruido.encode("utf-8"),
            prompt_original.encode("utf-8"),
        )

    def test_amostrar_categorica_respeita_pesos_com_seed_fixa(self):
        pesos = {"a": 1, "b": 3}

        seq_1 = [
            amostrar_categorica(pesos, np.random.default_rng(1234))
            for _ in range(5)
        ]
        seq_2 = [
            amostrar_categorica(pesos, np.random.default_rng(1234))
            for _ in range(5)
        ]
        self.assertEqual(seq_1, seq_2)

        rng = np.random.default_rng(99)
        amostras = [amostrar_categorica(pesos, rng) for _ in range(4000)]
        proporcao_b = amostras.count("b") / len(amostras)

        self.assertIn("a", amostras)
        self.assertIn("b", amostras)
        self.assertGreater(proporcao_b, 0.68)
        self.assertLess(proporcao_b, 0.82)

    def test_obter_pesos_retorna_default_quando_necessario(self):
        spec = {
            "tipo": "categorica",
            "depende_de": "persona_id",
            "pesos_condicionais": {
                "ana_beatriz_silva": {"rapida": 1, "media": 2},
                "_default": {"rapida": 3, "media": 4},
            },
        }

        self.assertEqual(
            obter_pesos(spec, {"persona_id": "ana_beatriz_silva"}),
            {"rapida": 1, "media": 2},
        )
        self.assertEqual(
            obter_pesos(spec, {"persona_id": "slug_inexistente"}),
            {"rapida": 3, "media": 4},
        )

    def test_amostrar_categorica_rejeita_pesos_invalidos(self):
        with self.assertRaises(ValueError):
            amostrar_categorica({}, np.random.default_rng(1))

        with self.assertRaises(ValueError):
            amostrar_categorica({"a": 0, "b": 1}, np.random.default_rng(1))

    def test_obter_pesos_falha_sem_pai_ou_sem_default(self):
        spec = {
            "tipo": "categorica",
            "depende_de": "offset",
            "pesos_condicionais": {
                "horario-comercial": {"true": 1, "false": 9},
            },
        }

        with self.assertRaises(KeyError):
            obter_pesos(spec, {})

        with self.assertRaises(KeyError):
            obter_pesos(spec, {"offset": "noite"})

        self.assertEqual(
            obter_pesos(
                {
                    "tipo": "bernoulli",
                    "depende_de": "weekend",
                    "pesos_condicionais": {
                        "true": {"true": 8, "false": 2},
                        "_default": {"true": 1, "false": 9},
                    },
                },
                {"weekend": True},
            ),
            {"true": 8, "false": 2},
        )

    def test_gerar_simulacoes_aplica_min_por_persona(self):
        config = {
            "template_prompt": "{identidade} [[como agir]] {como_agir} [[missão]] {missao}",
            "personas": {
                "a": {"identidade": "A", "como_agir": "agir", "missao": "missao"},
                "b": {"identidade": "B", "como_agir": "agir", "missao": "missao"},
            },
            "amostragem": {
                "n": 4,
                "seed": 7,
                "metodo": "ancestral",
                "dag_ordem": ["persona_id", "duracao", "offset", "weekend"],
                "variaveis": {
                    "persona_id": {
                        "tipo": "categorica",
                        "depende_de": None,
                        "pesos": {"a": 4, "b": 1},
                    },
                    "duracao": {
                        "tipo": "categorica",
                        "depende_de": "persona_id",
                        "pesos_condicionais": {
                            "_default": {"rapida": 1, "media": 1, "lenta": 1}
                        },
                    },
                    "offset": {
                        "tipo": "categorica",
                        "depende_de": "persona_id",
                        "pesos_condicionais": {
                            "_default": {"horario-comercial": 1, "noite": 1}
                        },
                    },
                    "weekend": {
                        "tipo": "bernoulli",
                        "depende_de": "offset",
                        "pesos_condicionais": {
                            "horario-comercial": {"true": 1, "false": 9},
                            "noite": {"true": 3, "false": 7},
                        },
                    },
                },
                "restricoes": {"min_por_persona": 2},
            },
        }

        simulacoes = gerar_simulacoes(config)
        contagem = {}
        for simulacao in simulacoes:
            contagem[simulacao["persona_id"]] = contagem.get(simulacao["persona_id"], 0) + 1
            self.assertIsInstance(simulacao["weekend"], bool)

        self.assertEqual(sum(contagem.values()), 4)
        self.assertGreaterEqual(contagem["a"], 2)
        self.assertGreaterEqual(contagem["b"], 2)
