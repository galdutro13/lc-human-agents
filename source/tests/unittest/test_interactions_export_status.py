import json
import sqlite3
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tools.enxame_usuario import resume_state
from tools.visualizador_interacoes.backend import main as backend_main


class TestInteractionsExportStatus(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "checkpoints.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                type TEXT,
                checkpoint BLOB,
                metadata BLOB,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE writes (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                type TEXT,
                value BLOB,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            )
            """
        )
        resume_state.ensure_schema(conn)
        self.run_id = resume_state.create_run(
            conn,
            prompts_file_hash="abc",
            prompts_file_path="/tmp/prompts.json",
            passes=1,
            instances=[
                {
                    "instance_key": "pass-0001:simulation-000001",
                    "simulation_id": 1,
                    "pass_index": 1,
                    "queue_index": 1,
                    "persona_id": "ana",
                }
            ],
            args={},
        )
        resume_state.mark_instance_not_finished(
            conn,
            run_id=self.run_id,
            instance_key="pass-0001:simulation-000001",
            error="interrompida",
        )
        conn.close()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_json_zip_inclui_placeholder_not_finished_sem_checkpoint(self):
        client = TestClient(backend_main.app)
        with patch.object(backend_main, "DATABASE_PATH", str(self.db_path)):
            response = client.get("/interactions/export/all_json_zip")

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(BytesIO(response.content), "r") as zip_file:
            names = zip_file.namelist()
            self.assertIn("index.json", names)
            conversation_names = [name for name in names if name.startswith("conversa_")]
            self.assertEqual(len(conversation_names), 1)
            placeholder = json.loads(zip_file.read(conversation_names[0]).decode("utf-8"))
            index = json.loads(zip_file.read("index.json").decode("utf-8"))

        self.assertEqual(placeholder["execution_status"], resume_state.STATUS_NOT_FINISHED)
        self.assertFalse(placeholder["finished"])
        self.assertTrue(placeholder["not_finished"])
        self.assertEqual(placeholder["messages"], [])
        self.assertEqual(
            index["conversations"][0]["execution_status"],
            resume_state.STATUS_NOT_FINISHED,
        )


if __name__ == "__main__":
    unittest.main()
