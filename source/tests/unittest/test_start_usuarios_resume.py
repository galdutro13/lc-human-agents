import tempfile
import unittest
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests

from source.tests.chatbot_test.usuario import UsuarioBot
from tools.enxame_usuario import resume_state
from tools.enxame_usuario.start_usuarios import (
    QueueAbortError,
    finalize_run_after_invocation,
    iniciar_usuario,
    is_queue_abort_error,
    run_parallel_bounded,
    run_sequential,
)


class FakeUsuarioBot:
    should_fail = False
    failure_by_persona = {}
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeUsuarioBot.calls.append(kwargs)

    def run(self, initial_query, max_iterations):
        failure = FakeUsuarioBot.failure_by_persona.get(self.kwargs["persona_id"])
        if failure:
            raise failure
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
        FakeUsuarioBot.failure_by_persona = {}
        FakeUsuarioBot.calls = []

    def _args(self, window_size=1):
        return SimpleNamespace(
            prompts_file="config_v4_4.json",
            passes=1,
            sequencial=False,
            window_size=window_size,
            api_url="http://example.test",
            break_probability=0.0,
            no_simulate_delays=True,
        )

    def _run_queue(self):
        return [
            {
                "instance_key": instance["instance_key"],
                "persona_id": instance["persona_id"],
                "prompt": "prompt",
                "typing_speed_wpm": 40.0,
                "thinking_time_range": (1.0, 2.0),
                "temporal_offset": timedelta(0),
            }
            for instance in self.instances
        ]

    def _http_error(self, status_code, body=""):
        response = requests.Response()
        response.status_code = status_code
        response.url = "http://example.test/api/message"
        response._content = body.encode("utf-8")
        return requests.HTTPError("erro http", response=response)

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

    def test_falha_individual_sequencial_continua_fila(self):
        FakeUsuarioBot.failure_by_persona = {"persona_ana": RuntimeError("falha individual")}

        with patch("tools.enxame_usuario.start_usuarios.UsuarioBot", FakeUsuarioBot):
            run_sequential(
                self._run_queue(),
                args=self._args(),
                run_id=self.run_id,
                db_path=str(self.db_path),
                break_range=(1.0, 2.0),
                use_thinking=False,
            )

        rows = self.conn.execute(
            """
            SELECT instance_key, status
            FROM simulation_instances
            WHERE run_id = ?
            ORDER BY queue_index
            """,
            (self.run_id,),
        ).fetchall()

        self.assertEqual(len(FakeUsuarioBot.calls), 2)
        self.assertEqual(rows[0]["status"], resume_state.STATUS_NOT_FINISHED)
        self.assertEqual(rows[1]["status"], resume_state.STATUS_COMPLETED)

    def test_connection_error_aborta_sequencial_e_preserva_pending(self):
        FakeUsuarioBot.failure_by_persona = {"persona_ana": requests.ConnectionError("offline")}

        with patch("tools.enxame_usuario.start_usuarios.UsuarioBot", FakeUsuarioBot):
            with self.assertRaises(QueueAbortError):
                run_sequential(
                    self._run_queue(),
                    args=self._args(),
                    run_id=self.run_id,
                    db_path=str(self.db_path),
                    break_range=(1.0, 2.0),
                    use_thinking=False,
                )

        rows = self.conn.execute(
            """
            SELECT instance_key, status, error
            FROM simulation_instances
            WHERE run_id = ?
            ORDER BY queue_index
            """,
            (self.run_id,),
        ).fetchall()
        pending = resume_state.get_pending_instances(self.conn, self.run_id)

        self.assertEqual(len(FakeUsuarioBot.calls), 1)
        self.assertEqual(rows[0]["status"], resume_state.STATUS_NOT_FINISHED)
        self.assertTrue(rows[0]["error"].startswith("QUEUE_ABORT:"))
        self.assertEqual(rows[1]["status"], resume_state.STATUS_PENDING)
        self.assertEqual([row["instance_key"] for row in pending], ["pass-0001:simulation-000002"])

    def test_http_429_auth_e_quota_sao_classificados_como_abort(self):
        self.assertTrue(is_queue_abort_error(self._http_error(429)))
        self.assertTrue(is_queue_abort_error(self._http_error(401, '{"error":{"code":"invalid_api_key"}}')))
        self.assertTrue(is_queue_abort_error(self._http_error(500, '{"error":"insufficient_quota"}')))
        self.assertTrue(
            is_queue_abort_error(
                RuntimeError(
                    "Error code: 401 - {'error': {'message': 'Incorrect API key provided', "
                    "'code': 'invalid_api_key'}, 'status': 401}"
                )
            )
        )
        self.assertFalse(is_queue_abort_error(RuntimeError("quota local configurada incorretamente")))

    def test_parallel_aborta_sem_submeter_novos_itens(self):
        FakeUsuarioBot.failure_by_persona = {"persona_ana": requests.ConnectionError("offline")}

        with patch("tools.enxame_usuario.start_usuarios.UsuarioBot", FakeUsuarioBot):
            with self.assertRaises(QueueAbortError):
                run_parallel_bounded(
                    self._run_queue(),
                    args=self._args(window_size=1),
                    run_id=self.run_id,
                    db_path=str(self.db_path),
                    break_range=(1.0, 2.0),
                    use_thinking=False,
                )

        rows = self.conn.execute(
            """
            SELECT instance_key, status
            FROM simulation_instances
            WHERE run_id = ?
            ORDER BY queue_index
            """,
            (self.run_id,),
        ).fetchall()

        self.assertEqual(len(FakeUsuarioBot.calls), 1)
        self.assertEqual(rows[0]["status"], resume_state.STATUS_NOT_FINISHED)
        self.assertEqual(rows[1]["status"], resume_state.STATUS_PENDING)

    def test_send_to_bancobot_repropaga_request_exception(self):
        bot = UsuarioBot.__new__(UsuarioBot)
        bot.api_url = "http://example.test"
        bot.persona_id = "persona_ana"
        bot.simulated_timestamp = datetime.now()
        bot.thinking_time = 0
        bot.last_break_time = 0
        bot.session_id = None

        with patch("source.tests.chatbot_test.usuario.requests.post", side_effect=requests.ConnectionError("offline")) as post:
            with self.assertRaises(requests.ConnectionError):
                bot._send_to_bancobot("ola")

        self.assertEqual(post.call_args.kwargs["timeout"], 30)

    def test_run_fecha_sessao_quando_send_falha(self):
        message = SimpleNamespace(
            content="ola",
            additional_kwargs={"timing_metadata": {}},
        )
        bot = UsuarioBot.__new__(UsuarioBot)
        bot.temporal_offset = timedelta(0)
        bot.simulate_delays = False
        bot.session_id = "session-a"
        bot.typing_speed_wpm = 40.0
        bot.thinking_time = 0
        bot.total_typing_time = 0
        bot.last_break_time = 0
        bot._calculate_thinking_time = lambda: 0
        bot.process_query_with_output = lambda query: {"messages": [message]}
        bot._get_typing_time_from_response = lambda output: 0
        bot._get_simulated_timestamp = lambda output: datetime.now()
        bot._send_to_bancobot = lambda response: (_ for _ in ()).throw(requests.ConnectionError("offline"))

        with patch.object(bot, "_finish_bancobot_session") as finish:
            with self.assertRaises(requests.ConnectionError):
                bot.run("inicio", max_iterations=1)

        finish.assert_called_once()

    def test_abort_sem_pendentes_preserva_run_interrupted(self):
        resume_state.mark_instance_running(
            self.conn,
            run_id=self.run_id,
            instance_key="pass-0001:simulation-000001",
            thread_id="thread-a",
        )
        resume_state.mark_instance_not_finished(
            self.conn,
            run_id=self.run_id,
            instance_key="pass-0001:simulation-000001",
            error="QUEUE_ABORT: offline",
        )
        resume_state.mark_instance_running(
            self.conn,
            run_id=self.run_id,
            instance_key="pass-0001:simulation-000002",
            thread_id="thread-b",
        )
        resume_state.mark_instance_completed(
            self.conn,
            run_id=self.run_id,
            instance_key="pass-0001:simulation-000002",
        )
        resume_state.interrupt_run(self.conn, self.run_id)

        completed = finalize_run_after_invocation(str(self.db_path), self.run_id, run_interrupted=True)
        row = self.conn.execute(
            "SELECT status FROM simulation_runs WHERE run_id = ?",
            (self.run_id,),
        ).fetchone()

        self.assertIsNone(completed)
        self.assertEqual(row["status"], resume_state.RUN_STATUS_INTERRUPTED)

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
