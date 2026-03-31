import unittest

from source.simulations import canonicalize_prompt, load_simulation_document, load_simulations


class TestPersonasV3Loader(unittest.TestCase):
    def test_canonicalize_prompt_is_deterministic(self):
        prompt = "Voc\u00ea \u00e9 Ana\r\nlinha final   \r\n"
        self.assertEqual(canonicalize_prompt(prompt), "Voc\u00ea \u00e9 Ana\nlinha final")

    def test_load_simulations_resolves_personas_and_configs(self):
        simulations = load_simulations("data/migrated/personas_tf/personas_tf.v3.json")
        self.assertEqual(len(simulations), 300)
        self.assertEqual(len({simulation.persona_id for simulation in simulations}), 21)
        self.assertEqual(len({simulation.config_id for simulation in simulations}), 11)

        first = simulations[0]
        self.assertEqual(first.schema_version, "3.0")
        self.assertTrue(first.persona_id.startswith("per::personas_tf::"))
        self.assertTrue(first.config_id.startswith("cfg::"))
        self.assertTrue(first.politica_id.startswith("pol::personas_tf::"))
        self.assertIn("sim_id", first.simulation_metadata)
        self.assertEqual(first.simulation_metadata["sim_id"], first.sim_id)

    def test_partial_prompt_catalog_migration_remains_valid(self):
        document = load_simulation_document("data/migrated/personas_carlos/personas_carlos.v3.json")
        self.assertEqual(document.versao_schema, "3.0")
        self.assertGreaterEqual(len(document.personas), 1)
        self.assertEqual(document.configuracoes, {})
        self.assertEqual(document.politicas_amostrais, {})
        self.assertEqual(document.simulacoes, [])
