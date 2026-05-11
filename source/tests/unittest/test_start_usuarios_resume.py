import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.enxame_usuario import resume_state
from tools.enxame_usuario.start_usuarios import iniciar_usuario, run_parallel_bounded


class FakeUsuarioBot:
    should_fail = False
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeUsuarioBot.calls.append(kwargs)

    def run(self, initial_query, max_iterations):
        if FakeUsuarioBot.should_fail:
            raise RuntimeError("falha simulada")


class FakeFuture:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class TestStartUsuariosResume(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "checkpoints.db"
        self.conn = resume_state.connect(self.db_path)
        resume_state.ensure_schema(self.conn)
        self.instances = [
            {
                "instance_key": "pass-0001:simulation-000001",
                "simulation_id": 1,
                "pass_index": 1,
                "queue_index": 1,
                "persona_id": "ana",
            },
            {
                "instance_key": "pass-0001:simulation-000002",
                "simulation_id": 2,
                "pass_index": 1,
                "queue_index": 2,
                "persona_id": "bia",
            },
        ]
        self.run_id = resume_state.create_run(
            self.conn,
            prompts_file_hash="abc",
            prompts_file_path="/tmp/prompts.json",
            passes=1,
            instances=self.instances,
            args={},
        )

    def tearDown(self):
        self.conn.close()
        self.tmpdir.cleanup()
        FakeUsuarioBot.should_fail = False
        FakeUsuarioBot.calls = []

    def test_iniciar_usuario_marca_completed_e_passa_thread_id(self):
        with patch("tools.enxame_usuario.start_usuarios.UsuarioBot", FakeUsuarioBot):
            ok = iniciar_usuario(
                "ana",
                False,
                "prompt",
                api_url="http://example.test",
                typing_speed_wpm=40.0,
                thinking_time_range=(1.0, 2.0),
                break_probability=0.0,
                break_time_range=(1.0, 2.0),
                simulate_delays=False,
                temporal_offset=timedelta(0),
                run_id=self.run_id,
                instance_key="pass-0001:simulation-000001",
                db_path=str(self.db_path),
            )

        row = self.conn.execute(
            """
            SELECT status, thread_id
            FROM simulation_instances
            WHERE run_id = ? AND instance_key = ?
            """,
            (self.run_id, "pass-0001:simulation-000001"),
        ).fetchone()

        self.assertTrue(ok)
        self.assertEqual(row["status"], resume_state.STATUS_COMPLETED)
        self.assertTrue(row["thread_id"])
        self.assertEqual(FakeUsuarioBot.calls[0]["thread_id"], row["thread_id"])

    def test_iniciar_usuario_marca_not_finished_em_falha_e_resume_preserva(self):
        FakeUsuarioBot.should_fail = True
        with patch("tools.enxame_usuario.start_usuarios.UsuarioBot", FakeUsuarioBot):
            ok = iniciar_usuario(
                "ana",
                False,
                "prompt",
                api_url="http://example.test",
                typing_speed_wpm=40.0,
                thinking_time_range=(1.0, 2.0),
                break_probability=0.0,
                break_time_range=(1.0, 2.0),
                simulate_delays=False,
                temporal_offset=timedelta(0),
                run_id=self.run_id,
                instance_key="pass-0001:simulation-000001",
                db_path=str(self.db_path),
            )

        pending = resume_state.get_pending_instances(self.conn, self.run_id)
        rows = self.conn.execute(
            """
            SELECT instance_key, status
            FROM simulation_instances
            WHERE run_id = ?
            ORDER BY queue_index
            """,
            (self.run_id,),
        ).fetchall()

        self.assertFalse(ok)
        self.assertEqual(rows[0]["status"], resume_state.STATUS_NOT_FINISHED)
        self.assertEqual([row["instance_key"] for row in pending], ["pass-0001:simulation-000002"])

    def test_parallel_keyboard_interrupt_marca_running_sem_esperar_executor(self):
        resume_state.mark_instance_running(
            self.conn,
            run_id=self.run_id,
            instance_key="pass-0001:simulation-000001",
            thread_id="thread-a",
        )
        fake_future = FakeFuture()
        args = SimpleNamespace(
            window_size=1,
            api_url="http://example.test",
            break_probability=0.0,
            no_simulate_delays=True,
        )
        run_queue = [
            {
                "instance_key": "pass-0001:simulation-000001",
                "persona_id": "ana",
                "prompt": "prompt",
                "typing_speed_wpm": 40.0,
                "thinking_time_range": (1.0, 2.0),
                "temporal_offset": timedelta(0),
            }
        ]

        with (
            patch("tools.enxame_usuario.start_usuarios.submit_usuario", return_value=fake_future),
            patch("tools.enxame_usuario.start_usuarios.wait", side_effect=KeyboardInterrupt),
        ):
            with self.assertRaises(SystemExit) as raised:
                run_parallel_bounded(
                    run_queue,
                    args=args,
                    run_id=self.run_id,
                    db_path=str(self.db_path),
                    break_range=(1.0, 2.0),
                    use_thinking=False,
                )

        row = self.conn.execute(
            """
            SELECT status
            FROM simulation_instances
            WHERE run_id = ? AND instance_key = ?
            """,
            (self.run_id, "pass-0001:simulation-000001"),
        ).fetchone()

        self.assertEqual(raised.exception.code, 130)
        self.assertTrue(fake_future.cancelled)
        self.assertEqual(row["status"], resume_state.STATUS_NOT_FINISHED)


if __name__ == "__main__":
    unittest.main()
