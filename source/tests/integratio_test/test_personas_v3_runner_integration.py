import unittest
from unittest.mock import MagicMock, patch

from source.simulations import load_simulations
from tools.enxame_usuario.start_usuarios import build_simulation_execution_config, iniciar_usuario


class TestPersonasV3RunnerIntegration(unittest.TestCase):
    def test_build_execution_config_from_resolved_simulation(self):
        simulation = load_simulations("data/migrated/personas/personas.v3.json")[0]
        prompt, typing_speed, thinking_range, temporal_offset = build_simulation_execution_config(simulation)

        self.assertIn("Carlos Ferreira", prompt)
        self.assertGreater(typing_speed, 0)
        self.assertEqual(len(thinking_range), 2)
        self.assertGreaterEqual(thinking_range[0], 0)
        self.assertGreaterEqual(temporal_offset.total_seconds(), 0)

    @patch("tools.enxame_usuario.start_usuarios.UsuarioBot")
    def test_iniciar_usuario_uses_real_persona_id_and_structured_metadata(self, usuario_bot_cls):
        simulation = load_simulations("data/migrated/personas/personas.v3.json")[0]
        bot_instance = MagicMock()
        usuario_bot_cls.return_value = bot_instance

        iniciar_usuario(
            simulation.persona_id,
            False,
            simulation.prompt,
            simulation_metadata=simulation.simulation_metadata,
            api_url="http://localhost:8080",
            typing_speed_wpm=40.0,
            thinking_time_range=(2.0, 4.0),
            break_probability=0.0,
            break_time_range=(0.0, 0.0),
            simulate_delays=False,
        )

        kwargs = usuario_bot_cls.call_args.kwargs
        self.assertEqual(kwargs["persona_id"], simulation.persona_id)
        self.assertEqual(kwargs["simulation_metadata"], simulation.simulation_metadata)
        bot_instance.run.assert_called_once()
