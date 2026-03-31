import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from source.simulations import load_simulation_document, validate_simulation_document


class TestPersonasV3Schema(unittest.TestCase):
    def test_generated_schema_validates_migrated_document(self):
        schema = json.loads(Path("data/migrated/simulation_schema_v3.json").read_text(encoding="utf-8"))
        document = json.loads(Path("data/migrated/personas_tf/personas_tf.v3.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(document)

    def test_pydantic_validation_accepts_migrated_document(self):
        document = load_simulation_document("data/migrated/personas_tf/personas_tf.v3.json")
        self.assertEqual(document.versao_schema, "3.0")
        self.assertEqual(len(document.simulacoes), 300)
        self.assertEqual(len(document.personas), 21)
        self.assertEqual(len(document.configuracoes), 11)

    def test_rejects_broken_reference(self):
        document = json.loads(Path("data/migrated/personas/personas.v3.json").read_text(encoding="utf-8"))
        document["simulacoes"][0]["persona_id"] = "per::missing::deadbeef"

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(json.dumps(document, ensure_ascii=False))
            temp_path = temp_file.name

        try:
            with self.assertRaises(ValueError):
                validate_simulation_document(load_simulation_document(temp_path))
        finally:
            Path(temp_path).unlink(missing_ok=True)
