import json
import unittest
from pathlib import Path

from source.simulation_config import (
    DEFAULT_TEMPLATE_PROMPT,
    extract_personas_from_legacy,
    montar_prompt,
    parse_prompt_monolitico,
    slugify_persona_name,
)


ROOT = Path(__file__).resolve().parents[3]
LEGACY_PATH = ROOT / "personas_tf.json"


class TestMigrationParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with LEGACY_PATH.open("r", encoding="utf-8") as arquivo:
            cls.legacy = json.load(arquivo)

    def test_parse_prompt_monolitico_preserva_subcampos(self):
        for registro in self.legacy.values():
            partes = parse_prompt_monolitico(registro["persona"])
            reconstruido = montar_prompt(partes, partes["template_prompt"])
            self.assertEqual(reconstruido, registro["persona"])

    def test_extract_personas_from_legacy_deduplica_e_slugifica(self):
        personas, entradas, template_prompt = extract_personas_from_legacy(self.legacy)

        self.assertEqual(len(personas), 20)
        self.assertEqual(len(entradas), 300)
        self.assertEqual(template_prompt, DEFAULT_TEMPLATE_PROMPT)
        self.assertIn("ana_beatriz_silva", personas)
        self.assertIn("antonia_silveira", personas)
        self.assertIn("jose_carlos_da_silva", personas)

    def test_slugify_persona_name_remove_acentos(self):
        self.assertEqual(slugify_persona_name("Antônia Silveira"), "antonia_silveira")
        self.assertEqual(slugify_persona_name("João Pedro Oliveira"), "joao_pedro_oliveira")
