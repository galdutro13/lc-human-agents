import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.enxame_usuario import resume_state


class TestResumeState(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "checkpoints.db"
        self.conn = resume_state.connect(self.db_path)
        resume_state.ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmpdir.cleanup()

    def _instances(self):
        return [
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

    def test_create_run_materializa_instancias_pendentes(self):
        run_id = resume_state.create_run(
            self.conn,
            prompts_file_hash="abc",
            prompts_file_path="/tmp/prompts.json",
            passes=1,
            instances=self._instances(),
            args={"passes": 1},
        )

        run = resume_state.find_resume_run(
            self.conn,
            prompts_file_hash="abc",
            passes=1,
        )
        pending = resume_state.get_pending_instances(self.conn, run_id)

        self.assertEqual(run["run_id"], run_id)
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending[0]["status"], resume_state.STATUS_PENDING)

    def test_transicoes_de_status_e_finalizacao(self):
        run_id = resume_state.create_run(
            self.conn,
            prompts_file_hash="abc",
            prompts_file_path="/tmp/prompts.json",
            passes=1,
            instances=self._instances(),
            args={},
        )

        resume_state.mark_instance_running(
            self.conn,
            run_id=run_id,
            instance_key="pass-0001:simulation-000001",
            thread_id="thread-a",
        )
        resume_state.mark_instance_completed(
            self.conn,
            run_id=run_id,
            instance_key="pass-0001:simulation-000001",
        )
        resume_state.mark_instance_running(
            self.conn,
            run_id=run_id,
            instance_key="pass-0001:simulation-000002",
            thread_id="thread-b",
        )
        resume_state.mark_instance_not_finished(
            self.conn,
            run_id=run_id,
            instance_key="pass-0001:simulation-000002",
            error="boom",
        )

        self.assertTrue(resume_state.finalize_run_if_no_pending(self.conn, run_id))
        row = self.conn.execute(
            "SELECT status FROM simulation_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        self.assertEqual(row["status"], resume_state.RUN_STATUS_COMPLETED)

    def test_resume_converte_running_antigo_para_not_finished(self):
        run_id = resume_state.create_run(
            self.conn,
            prompts_file_hash="abc",
            prompts_file_path="/tmp/prompts.json",
            passes=1,
            instances=self._instances(),
            args={},
        )
        resume_state.mark_instance_running(
            self.conn,
            run_id=run_id,
            instance_key="pass-0001:simulation-000001",
            thread_id="thread-a",
        )

        changed = resume_state.mark_stale_running_instances_not_finished(self.conn, run_id)
        rows = self.conn.execute(
            """
            SELECT instance_key, status
            FROM simulation_instances
            WHERE run_id = ?
            ORDER BY queue_index
            """,
            (run_id,),
        ).fetchall()

        self.assertEqual(changed, 1)
        self.assertEqual(rows[0]["status"], resume_state.STATUS_NOT_FINISHED)
        self.assertEqual(rows[1]["status"], resume_state.STATUS_PENDING)

    def test_completed_run_nao_e_elegivel_para_resume(self):
        run_id = resume_state.create_run(
            self.conn,
            prompts_file_hash="abc",
            prompts_file_path="/tmp/prompts.json",
            passes=1,
            instances=self._instances()[:1],
            args={},
        )
        resume_state.mark_instance_running(
            self.conn,
            run_id=run_id,
            instance_key="pass-0001:simulation-000001",
            thread_id="thread-a",
        )
        resume_state.mark_instance_completed(
            self.conn,
            run_id=run_id,
            instance_key="pass-0001:simulation-000001",
        )
        resume_state.finalize_run_if_no_pending(self.conn, run_id)

        self.assertIsNone(
            resume_state.find_resume_run(
                self.conn,
                prompts_file_hash="abc",
                passes=1,
            )
        )

    def test_execution_status_fields_para_legado_e_not_finished(self):
        legacy = resume_state.execution_status_fields(None)
        self.assertEqual(legacy["execution_status"], "unknown")
        self.assertIsNone(legacy["finished"])

        row = {
            "run_id": "run",
            "simulation_id": 1,
            "pass_index": 1,
            "queue_index": 1,
            "status": resume_state.STATUS_NOT_FINISHED,
        }
        status = resume_state.execution_status_fields(row)
        self.assertFalse(status["finished"])
        self.assertTrue(status["not_finished"])


if __name__ == "__main__":
    unittest.main()
