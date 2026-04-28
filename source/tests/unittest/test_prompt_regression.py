import json
import unittest
from pathlib import Path

from source.simulation_config import carregar_config_v42, montar_prompt


ROOT = Path(__file__).resolve().parents[3]
V42_PATH = ROOT / "config_v4_2.json"
LEGACY_V3_PATH = ROOT / "source/tests/fixtures/legacy/config_v3.json"
MAPPING_PATH = ROOT / "source/tests/fixtures/legacy/prompt_mission_map_v42.json"
SPECIAL_CASES = {
    "ana_beatriz_silva": "m01_cartao_planejamento_estudio",
    "carla_mendes": "m02_cartao_revisao_tarifas_beneficios",
    "carlos_ferreira": "m03_cartao_limite_vencimento_melhor_dia",
}


class TestPromptRegressionV42(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config_v42 = carregar_config_v42(V42_PATH)
        cls.legacy_v3 = json.loads(LEGACY_V3_PATH.read_text(encoding="utf-8"))
        cls.mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))

    def test_personas_originais_preservam_identidade_e_como_agir(self):
        for persona_id in self.mapping:
            self.assertEqual(
                self.config_v42["personas"][persona_id]["identidade"],
                self.legacy_v3["personas"][persona_id]["identidade"],
            )
            self.assertEqual(
                self.config_v42["personas"][persona_id]["como_agir"],
                self.legacy_v3["personas"][persona_id]["como_agir"],
            )

    def test_17_prompts_mantem_string_match_exato(self):
        for persona_id, missao_id in self.mapping.items():
            if persona_id in SPECIAL_CASES:
                continue
            prompt_v42 = montar_prompt(
                self.config_v42["personas"][persona_id],
                self.config_v42["missoes"][missao_id],
                self.config_v42["template_prompt"],
            )
            prompt_v3 = self.legacy_v3["template_prompt"].format(
                identidade=self.legacy_v3["personas"][persona_id]["identidade"],
                como_agir=self.legacy_v3["personas"][persona_id]["como_agir"],
                missao=self.legacy_v3["personas"][persona_id]["missao"],
            )
            self.assertEqual(prompt_v42, prompt_v3)

    def test_3_prompts_mudados_tem_mapeamento_explicito(self):
        for persona_id, missao_id in SPECIAL_CASES.items():
            self.assertEqual(self.mapping[persona_id], missao_id)

            prompt_v42 = montar_prompt(
                self.config_v42["personas"][persona_id],
                self.config_v42["missoes"][missao_id],
                self.config_v42["template_prompt"],
            )
            prompt_v3 = self.legacy_v3["template_prompt"].format(
                identidade=self.legacy_v3["personas"][persona_id]["identidade"],
                como_agir=self.legacy_v3["personas"][persona_id]["como_agir"],
                missao=self.legacy_v3["personas"][persona_id]["missao"],
            )

            self.assertNotEqual(prompt_v42, prompt_v3)
            self.assertIn(self.config_v42["missoes"][missao_id]["missao"], prompt_v42)
