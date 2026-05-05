import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
V43_PATH = ROOT / "config_v4_3.json"
SCRIPT_PATH = ROOT / "tools/enxame_usuario/export_simulation_audit.py"
EXPECTED_N = json.loads(V43_PATH.read_text(encoding="utf-8"))["amostragem"]["n"]


class TestExportSimulationAuditIntegration(unittest.TestCase):
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

    def test_export_script_gera_json_de_auditoria(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "audit.json"
            result = self._run_script(
                "--config-file",
                str(V43_PATH),
                "--output-json",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
            self.assertTrue(output_path.exists())

            relatorio = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(relatorio["versao_schema"], "4.3")
            self.assertEqual(relatorio["n"], EXPECTED_N)
            self.assertTrue(all(relatorio["checks"].values()))
            self.assertIn("pesos_brutos_dia_relativo", relatorio)
            self.assertIn("pesos_percentuais_dia_relativo_derivados", relatorio)
            self.assertIn("dia_relativo", relatorio["cotas_calculadas"])
            self.assertIn("persona_id", relatorio["contagens_observadas"])
