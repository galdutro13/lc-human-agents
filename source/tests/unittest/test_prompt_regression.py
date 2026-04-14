import json
import unittest
from pathlib import Path

from source.simulation_config import (
    auditar_reconstrucao_prompts,
    extract_personas_from_legacy,
    montar_prompt,
)


ROOT = Path(__file__).resolve().parents[3]
LEGACY_PATH = ROOT / "personas_tf.json"
V3_PATH = ROOT / "config_v3.json"


class TestPromptRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with LEGACY_PATH.open("r", encoding="utf-8") as arquivo:
            cls.legacy = json.load(arquivo)
        with V3_PATH.open("r", encoding="utf-8") as arquivo:
            cls.config_v3 = json.load(arquivo)
        cls.personas_legado, cls.entradas_legado, _ = extract_personas_from_legacy(cls.legacy)

    def test_regressao_prompts_das_20_personas(self):
        prompts_representativos = {}
        for entrada in self.entradas_legado:
            prompts_representativos.setdefault(entrada["persona_id"], entrada["persona"])

        self.assertEqual(self.personas_legado, self.config_v3["personas"])
        for persona_id, persona in self.config_v3["personas"].items():
            prompt = montar_prompt(persona, self.config_v3["template_prompt"])
            self.assertEqual(prompt, prompts_representativos[persona_id])

    def test_regressao_prompt_audita_300_entradas(self):
        auditoria = auditar_reconstrucao_prompts(
            self.legacy,
            self.config_v3,
            self.entradas_legado,
        )

        self.assertEqual(auditoria["unique_persona_matches"], 20)
        self.assertEqual(auditoria["entry_matches"], 300)
        self.assertEqual(auditoria["mismatches"], [])
