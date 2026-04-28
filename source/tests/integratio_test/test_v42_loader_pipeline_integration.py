import unittest
from argparse import Namespace
from datetime import timedelta
from pathlib import Path

from source.simulation_config import (
    carregar_config_v42,
    gerar_simulacoes,
    validar_simulacoes_geradas,
)
from source.simulation_config.errors import ConfigValidationError
from tools.enxame_usuario.start_usuarios import parse_persona_config


ROOT = Path(__file__).resolve().parents[3]
V42_PATH = ROOT / "config_v4_2.json"
LEGACY_V3_PATH = ROOT / "source/tests/fixtures/legacy/config_v3.json"


class TestV42LoaderPipelineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.default_args = Namespace(
            typing_speed=40.0,
            thinking_min=2.0,
            thinking_max=10.0,
        )

    def test_pipeline_loader_gerador_e_parser(self):
        config = carregar_config_v42(V42_PATH)
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

    def test_loader_rejeita_v3(self):
        with self.assertRaisesRegex(ConfigValidationError, "Esperado '4.2'"):
            carregar_config_v42(LEGACY_V3_PATH)
