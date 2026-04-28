import unittest
from datetime import datetime
from pathlib import Path

from source.simulation_config import carregar_config_v42, gerar_simulacoes
from tools.enxame_usuario.simulation_projection import (
    CSV_FIELDNAMES,
    calculate_target_local_datetime,
    get_ritmo_parameters,
    normalize_preview_text,
    resolve_simulation_projection,
    truncate_preview,
)


ROOT = Path(__file__).resolve().parents[3]
V42_PATH = ROOT / "config_v4_2.json"


class TestSimulationProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = carregar_config_v42(V42_PATH)
        cls.simulacao = gerar_simulacoes(cls.config)[0]
        cls.now = datetime(2026, 4, 20, 8, 0, 0)

    def test_normalize_preview_text_colapsa_whitespace(self):
        self.assertEqual(
            normalize_preview_text("  linha 1\n\nlinha\t2   linha3  "),
            "linha 1 linha 2 linha3",
        )

    def test_truncate_preview_adiciona_ellipsis(self):
        self.assertEqual(truncate_preview("abcdef", 5), "ab...")
        self.assertEqual(truncate_preview("abc", 5), "abc")

    def test_get_ritmo_parameters_resolve_envelopes(self):
        self.assertEqual(
            get_ritmo_parameters("rapido"),
            {"typing_speed": 72.0, "thinking_min": 1.5, "thinking_max": 5.0},
        )
        self.assertEqual(
            get_ritmo_parameters("medio"),
            {"typing_speed": 42.0, "thinking_min": 4.0, "thinking_max": 11.0},
        )
        self.assertEqual(
            get_ritmo_parameters("lento"),
            {"typing_speed": 18.0, "thinking_min": 12.0, "thinking_max": 28.0},
        )

    def test_calculate_target_local_datetime_consistente_com_calendario(self):
        calendario = self.config["amostragem"]["variaveis"]["dia_relativo"]["calendario"]
        target = calculate_target_local_datetime(
            "d01",
            "manha",
            calendario,
            now=self.now,
        )
        self.assertIsNotNone(target)
        self.assertEqual(target.isoformat(timespec="seconds"), "2026-04-20T09:00:00")

    def test_resolve_simulation_projection_gera_colunas_esperadas(self):
        projection = resolve_simulation_projection(
            self.simulacao,
            self.config,
            now=self.now,
            prompt_preview_chars=60,
        )

        for field in CSV_FIELDNAMES:
            self.assertIn(field, projection)

        self.assertIn("prompt", projection)
        self.assertIn("thinking_time_range", projection)
        self.assertIn("temporal_offset", projection)
        self.assertEqual(
            projection["temporal_offset_seconds"],
            int(projection["temporal_offset"].total_seconds()),
        )
        self.assertLessEqual(len(projection["prompt_preview"]), 60)
        self.assertEqual(projection["id"], self.simulacao["id"])
