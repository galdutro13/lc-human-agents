from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


DATABASE_PATH = "checkpoints.db"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_NOT_FINISHED = "not_finished"

RUN_STATUS_RUNNING = "running"
RUN_STATUS_INTERRUPTED = "interrupted"
RUN_STATUS_COMPLETED = "completed"

ACTIVE_INSTANCE_STATUSES = (STATUS_PENDING, STATUS_RUNNING)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")


def calculate_file_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect(db_path: str | Path = DATABASE_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            run_id TEXT PRIMARY KEY,
            prompts_file_hash TEXT NOT NULL,
            prompts_file_path TEXT NOT NULL,
            passes INTEGER NOT NULL,
            total_instances INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            args_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_instances (
            run_id TEXT NOT NULL,
            instance_key TEXT NOT NULL,
            simulation_id INTEGER NOT NULL,
            pass_index INTEGER NOT NULL,
            queue_index INTEGER NOT NULL,
            persona_id TEXT NOT NULL,
            thread_id TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            error TEXT,
            PRIMARY KEY (run_id, instance_key),
            FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_simulation_runs_resume
        ON simulation_runs (prompts_file_hash, passes, status, created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_simulation_instances_thread_id
        ON simulation_instances (thread_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_simulation_instances_status
        ON simulation_instances (run_id, status, queue_index)
        """
    )
    conn.commit()


def _json_dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def create_run(
    conn: sqlite3.Connection,
    *,
    prompts_file_hash: str,
    prompts_file_path: str,
    passes: int,
    instances: Iterable[dict],
    args: dict,
) -> str:
    ensure_schema(conn)
    run_id = uuid.uuid4().hex
    now = utc_now_iso()
    instance_list = list(instances)

    with conn:
        conn.execute(
            """
            INSERT INTO simulation_runs (
                run_id, prompts_file_hash, prompts_file_path, passes,
                total_instances, status, created_at, updated_at, args_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                prompts_file_hash,
                prompts_file_path,
                int(passes),
                len(instance_list),
                RUN_STATUS_RUNNING,
                now,
                now,
                _json_dumps(args),
            ),
        )
        conn.executemany(
            """
            INSERT INTO simulation_instances (
                run_id, instance_key, simulation_id, pass_index, queue_index,
                persona_id, thread_id, status, created_at, updated_at,
                started_at, completed_at, error
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL, NULL, NULL)
            """,
            [
                (
                    run_id,
                    instance["instance_key"],
                    int(instance["simulation_id"]),
                    int(instance["pass_index"]),
                    int(instance["queue_index"]),
                    instance["persona_id"],
                    STATUS_PENDING,
                    now,
                    now,
                )
                for instance in instance_list
            ],
        )
    return run_id


def find_resume_run(
    conn: sqlite3.Connection,
    *,
    prompts_file_hash: str,
    passes: int,
) -> sqlite3.Row | None:
    ensure_schema(conn)
    cursor = conn.execute(
        """
        SELECT *
        FROM simulation_runs
        WHERE prompts_file_hash = ?
          AND passes = ?
          AND status != ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (prompts_file_hash, int(passes), RUN_STATUS_COMPLETED),
    )
    return cursor.fetchone()


def count_active_compatible_runs(
    conn: sqlite3.Connection,
    *,
    prompts_file_hash: str,
    passes: int,
) -> int:
    ensure_schema(conn)
    cursor = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM simulation_runs
        WHERE prompts_file_hash = ?
          AND passes = ?
          AND status != ?
        """,
        (prompts_file_hash, int(passes), RUN_STATUS_COMPLETED),
    )
    return int(cursor.fetchone()["total"])


def mark_stale_running_instances_not_finished(conn: sqlite3.Connection, run_id: str) -> int:
    ensure_schema(conn)
    now = utc_now_iso()
    with conn:
        cursor = conn.execute(
            """
            UPDATE simulation_instances
            SET status = ?,
                updated_at = ?,
                completed_at = COALESCE(completed_at, ?),
                error = COALESCE(error, ?)
            WHERE run_id = ?
              AND status = ?
            """,
            (
                STATUS_NOT_FINISHED,
                now,
                now,
                "Processo anterior terminou antes de marcar conclusão.",
                run_id,
                STATUS_RUNNING,
            ),
        )
        conn.execute(
            """
            UPDATE simulation_runs
            SET status = ?, updated_at = ?
            WHERE run_id = ?
            """,
            (RUN_STATUS_RUNNING, now, run_id),
        )
    return int(cursor.rowcount)


def get_pending_instances(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    ensure_schema(conn)
    cursor = conn.execute(
        """
        SELECT *
        FROM simulation_instances
        WHERE run_id = ?
          AND status = ?
        ORDER BY queue_index ASC
        """,
        (run_id, STATUS_PENDING),
    )
    return list(cursor.fetchall())


def mark_instance_running(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    instance_key: str,
    thread_id: str,
) -> None:
    ensure_schema(conn)
    now = utc_now_iso()
    with conn:
        conn.execute(
            """
            UPDATE simulation_instances
            SET status = ?,
                thread_id = ?,
                started_at = COALESCE(started_at, ?),
                updated_at = ?,
                error = NULL
            WHERE run_id = ?
              AND instance_key = ?
              AND status = ?
            """,
            (STATUS_RUNNING, thread_id, now, now, run_id, instance_key, STATUS_PENDING),
        )
        conn.execute(
            """
            UPDATE simulation_runs
            SET status = ?, updated_at = ?
            WHERE run_id = ?
            """,
            (RUN_STATUS_RUNNING, now, run_id),
        )


def mark_instance_completed(conn: sqlite3.Connection, *, run_id: str, instance_key: str) -> None:
    ensure_schema(conn)
    now = utc_now_iso()
    with conn:
        conn.execute(
            """
            UPDATE simulation_instances
            SET status = ?,
                updated_at = ?,
                completed_at = ?,
                error = NULL
            WHERE run_id = ?
              AND instance_key = ?
            """,
            (STATUS_COMPLETED, now, now, run_id, instance_key),
        )


def mark_instance_not_finished(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    instance_key: str,
    error: str | None = None,
) -> None:
    ensure_schema(conn)
    now = utc_now_iso()
    with conn:
        conn.execute(
            """
            UPDATE simulation_instances
            SET status = ?,
                updated_at = ?,
                completed_at = COALESCE(completed_at, ?),
                error = ?
            WHERE run_id = ?
              AND instance_key = ?
              AND status != ?
            """,
            (
                STATUS_NOT_FINISHED,
                now,
                now,
                (error or "Execução interrompida.")[:1000],
                run_id,
                instance_key,
                STATUS_COMPLETED,
            ),
        )


def finalize_run_if_no_pending(conn: sqlite3.Connection, run_id: str) -> bool:
    ensure_schema(conn)
    cursor = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM simulation_instances
        WHERE run_id = ?
          AND status IN (?, ?)
        """,
        (run_id, STATUS_PENDING, STATUS_RUNNING),
    )
    active_count = int(cursor.fetchone()["total"])
    now = utc_now_iso()
    with conn:
        conn.execute(
            """
            UPDATE simulation_runs
            SET status = ?, updated_at = ?
            WHERE run_id = ?
            """,
            (
                RUN_STATUS_COMPLETED if active_count == 0 else RUN_STATUS_INTERRUPTED,
                now,
                run_id,
            ),
        )
    return active_count == 0


def interrupt_run(conn: sqlite3.Connection, run_id: str) -> int:
    ensure_schema(conn)
    changed = mark_stale_running_instances_not_finished(conn, run_id)
    now = utc_now_iso()
    with conn:
        conn.execute(
            """
            UPDATE simulation_runs
            SET status = ?, updated_at = ?
            WHERE run_id = ?
            """,
            (RUN_STATUS_INTERRUPTED, now, run_id),
        )
    return changed


def execution_status_fields(row: sqlite3.Row | dict | None) -> dict:
    if row is None:
        return {
            "run_id": None,
            "simulation_id": None,
            "pass_index": None,
            "queue_index": None,
            "execution_status": "unknown",
            "finished": None,
            "not_finished": None,
        }

    status = row["status"]
    return {
        "run_id": row["run_id"],
        "simulation_id": row["simulation_id"],
        "pass_index": row["pass_index"],
        "queue_index": row["queue_index"],
        "execution_status": status,
        "finished": status == STATUS_COMPLETED,
        "not_finished": status == STATUS_NOT_FINISHED,
    }
