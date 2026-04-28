import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
V42_PATH = ROOT / "config_v4_2.json"
LEGACY_V4_PATH = ROOT / "source/tests/fixtures/legacy/config_v4_1.json"
SCRIPT_PATH = ROOT / "tools/enxame_usuario/export_simulation_preview.py"
EXPECTED_N = json.loads(V42_PATH.read_text(encoding="utf-8"))["amostragem"]["n"]


class TestExportSimulationPreviewIntegration(unittest.TestCase):
    def _run_script(self, *args, **kwargs):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            **kwargs,
        )

    def test_export_script_gera_csv_com_n_linhas(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "preview.csv"
            result = self._run_script(
                "--config-file",
                str(V42_PATH),
                "--output-csv",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
            self.assertTrue(output_path.exists())

            with output_path.open("r", encoding="utf-8-sig", newline="") as csvfile:
                reader = csv.DictReader(csvfile, delimiter=";")
                rows = list(reader)

            self.assertEqual(len(rows), EXPECTED_N)
            self.assertEqual(reader.fieldnames[0], "id")
            self.assertEqual(reader.fieldnames[-1], "prompt_preview")
            self.assertTrue(rows[0]["persona_id"])
            self.assertTrue(rows[-1]["missao_id"])
            self.assertTrue(rows[0]["offset"])
            self.assertTrue(rows[-1]["ritmo"])
            self.assertEqual(Counter(row["persona_id"] for row in rows).total(), EXPECTED_N)

    def test_export_script_rejeita_v41_legado(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "preview.csv"
            result = self._run_script(
                "--config-file",
                str(LEGACY_V4_PATH),
                "--output-csv",
                str(output_path),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Esperado '4.2'", result.stdout + result.stderr)

    def test_export_script_respeita_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "preview.csv"
            output_path.write_text("existing", encoding="utf-8")

            result = self._run_script(
                "--config-file",
                str(V42_PATH),
                "--output-csv",
                str(output_path),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--overwrite", result.stdout + result.stderr)

            overwrite_result = self._run_script(
                "--config-file",
                str(V42_PATH),
                "--output-csv",
                str(output_path),
                "--overwrite",
            )
            self.assertEqual(
                overwrite_result.returncode,
                0,
                msg=overwrite_result.stderr + overwrite_result.stdout,
            )
