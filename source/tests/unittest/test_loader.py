import json
import os
import tempfile
import unittest
from pathlib import Path

from source.simulation_config import carregar_simulacoes, detectar_versao
from source.simulation_config.loader import _validar_config_v1


ROOT = Path(__file__).resolve().parents[3]
LEGACY_PATH = ROOT / "personas_tf.json"
V3_PATH = ROOT / "config_v3.json"


class TestLoader(unittest.TestCase):
    def test_loader_detecta_v1_e_retorna_formato_legado(self):
        simulacoes = carregar_simulacoes(LEGACY_PATH)

        self.assertEqual(len(simulacoes), 300)
        primeira = simulacoes["1"]
        self.assertIsInstance(primeira["persona"], str)
        self.assertIsInstance(primeira["duração"], str)
        self.assertIsInstance(primeira["offset"], str)
        self.assertIsInstance(primeira["weekend"], bool)

    def test_loader_detecta_v3_e_exporta_mesma_interface(self):
        simulacoes = carregar_simulacoes(V3_PATH)

        self.assertEqual(len(simulacoes), 300)
        self.assertEqual(list(simulacoes.keys())[0], "1")
        self.assertEqual(list(simulacoes.keys())[-1], "300")
        primeira = simulacoes["1"]
        self.assertSetEqual(set(primeira.keys()), {"persona", "duração", "offset", "weekend"})
        self.assertIsInstance(primeira["persona"], str)
        self.assertIsInstance(primeira["weekend"], bool)

    def test_seed_reprodutivel_no_v3(self):
        primeira_execucao = carregar_simulacoes(V3_PATH)
        segunda_execucao = carregar_simulacoes(V3_PATH)

        self.assertEqual(
            json.dumps(primeira_execucao, ensure_ascii=False, sort_keys=True),
            json.dumps(segunda_execucao, ensure_ascii=False, sort_keys=True),
        )

    def test_detectar_versao(self):
        with LEGACY_PATH.open("r", encoding="utf-8") as arquivo:
            legacy = json.load(arquivo)
        with V3_PATH.open("r", encoding="utf-8") as arquivo:
            v3 = json.load(arquivo)

        self.assertEqual(detectar_versao(legacy), "1.0")
        self.assertEqual(detectar_versao(v3), "3.0")

    def test_detectar_versao_rejeita_entradas_invalidas(self):
        with self.assertRaisesRegex(Exception, "objeto JSON"):
            detectar_versao([])
        with self.assertRaisesRegex(Exception, "não suportada"):
            detectar_versao({"versao": "2.0"})

    def test_validacao_v1_rejeita_formas_invalidas(self):
        with self.assertRaisesRegex(Exception, "não vazio"):
            _validar_config_v1({})
        with self.assertRaisesRegex(Exception, "strings"):
            _validar_config_v1({1: {"persona": "ok"}})
        with self.assertRaisesRegex(Exception, "string ou objeto"):
            _validar_config_v1({"1": 123})
        with self.assertRaisesRegex(Exception, "campo 'persona'"):
            _validar_config_v1({"1": {}})

    def test_carregar_simulacoes_v1_invalido_falha(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8", delete=False) as tmp:
            json.dump({"1": {}}, tmp, ensure_ascii=False)
            tmp_path = tmp.name

        try:
            with self.assertRaisesRegex(Exception, "campo 'persona'"):
                carregar_simulacoes(tmp_path)
        finally:
            os.unlink(tmp_path)
