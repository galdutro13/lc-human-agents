import unittest
import copy
from argparse import Namespace
from datetime import timedelta
from pathlib import Path

from source.simulation_config import (
    carregar_config_v44,
    gerar_simulacoes,
    validar_simulacoes_geradas,
)
from source.simulation_config.errors import ConfigValidationError
from tools.enxame_usuario.start_usuarios import parse_persona_config


ROOT = Path(__file__).resolve().parents[3]
V44_PATH = ROOT / "config_v4_4.json"
LEGACY_V3_PATH = ROOT / "source/tests/fixtures/legacy/config_v3.json"
LEGACY_V42_PATH = ROOT / "source/tests/fixtures/legacy/config_v4_2.json"
LEGACY_V43_PATH = ROOT / "source/tests/fixtures/legacy/config_v4_3.json"


class TestV44LoaderPipelineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.default_args = Namespace(
            typing_speed=40.0,
            thinking_min=2.0,
            thinking_max=10.0,
        )

    def test_pipeline_loader_gerador_e_parser(self):
        config = carregar_config_v44(V44_PATH)
        simulacoes = gerar_simulacoes(config)
        validar_simulacoes_geradas(config, simulacoes)

        self.assertEqual(len(simulacoes), config["amostragem"]["n"])
        primeira = simulacoes[0]
        prompt, typing_speed, thinking_range, temporal_offset = parse_persona_config(
            primeira,
            config,
            self.default_args,
        )

        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt)
        self.assertIsInstance(typing_speed, float)
        self.assertEqual(len(thinking_range), 2)
        self.assertGreater(temporal_offset, timedelta(0))

    def test_pipeline_funciona_com_multiplos_ns(self):
        base_config = carregar_config_v44(V44_PATH)

        for n in (1, 7, 90, 6000, 6001):
            config = copy.deepcopy(base_config)
            config["amostragem"]["n"] = n
            simulacoes = gerar_simulacoes(config)
            validar_simulacoes_geradas(config, simulacoes)
            self.assertEqual(len(simulacoes), n)

    def test_loader_rejeita_v3(self):
        with self.assertRaisesRegex(ConfigValidationError, "Esperado '4.4'"):
            carregar_config_v44(LEGACY_V3_PATH)

    def test_loader_rejeita_v42(self):
        with self.assertRaisesRegex(ConfigValidationError, "Esperado '4.4'"):
            carregar_config_v44(LEGACY_V42_PATH)

    def test_loader_rejeita_v43(self):
        with self.assertRaisesRegex(ConfigValidationError, "Esperado '4.4'"):
            carregar_config_v44(LEGACY_V43_PATH)
