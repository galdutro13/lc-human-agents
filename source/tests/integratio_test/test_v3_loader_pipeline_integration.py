import json
import unittest
from argparse import Namespace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from source.simulation_config import carregar_simulacoes
from tools.enxame_usuario.start_usuarios import parse_persona_config


ROOT = Path(__file__).resolve().parents[3]
LEGACY_PATH = ROOT / "personas_tf.json"
V3_PATH = ROOT / "config_v3.json"


class TestV3LoaderPipelineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.default_args = Namespace(
            typing_speed=40.0,
            thinking_min=2.0,
            thinking_max=10.0,
        )
        with LEGACY_PATH.open("r", encoding="utf-8") as arquivo:
            cls.legacy_raw = json.load(arquivo)

    @patch(
        "tools.enxame_usuario.start_usuarios.calculate_temporal_offset",
        return_value=timedelta(hours=2),
    )
    def test_pipeline_start_usuarios_aceita_v1_e_v3_sem_patch_downstream(self, _mock_offset):
        simulacoes_v1 = carregar_simulacoes(LEGACY_PATH)
        simulacoes_v3 = carregar_simulacoes(V3_PATH)

        self.assertEqual(len(simulacoes_v1), 300)
        self.assertEqual(len(simulacoes_v3), 300)
        self.assertEqual(set(simulacoes_v1.keys()), set(simulacoes_v3.keys()))

        for simulacoes in (simulacoes_v1, simulacoes_v3):
            persona_id, persona_data = next(iter(simulacoes.items()))
            prompt, typing_speed, thinking_range, temporal_offset = parse_persona_config(
                persona_data,
                self.default_args,
            )

            self.assertTrue(persona_id.isdigit())
            self.assertIsInstance(prompt, str)
            self.assertTrue(prompt)
            self.assertIsInstance(typing_speed, float)
            self.assertEqual(len(thinking_range), 2)
            self.assertEqual(temporal_offset, timedelta(hours=2))
