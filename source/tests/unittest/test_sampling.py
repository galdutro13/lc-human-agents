import copy
import json
import runpy
import unittest
from pathlib import Path

from source.simulation_config import (
    alocar_maiores_restos,
    calcular_plano_de_cotas,
    calcular_pesos_brutos_dia_relativo,
    carregar_config_v43,
    gerar_relatorio_auditoria,
    gerar_simulacoes,
    montar_prompt,
    obter_pesos_condicionados,
)


ROOT = Path(__file__).resolve().parents[3]
V43_PATH = ROOT / "config_v4_3.json"
LEGACY_V41_PATH = ROOT / "source/tests/fixtures/legacy/config_v4_1.json"
ORIGINAL_SCRIPT_PATH = ROOT / "source/tests/fixtures/legacy/gerar_cotas_dia_relativo_90d.py"


class TestSamplingV43(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = carregar_config_v43(V43_PATH)

    def test_alocar_maiores_restos_soma_n_e_respeita_desempate(self):
        cotas = alocar_maiores_restos({"b": 1, "a": 1, "c": 1}, 2, ["b", "a", "c"])
        self.assertEqual(sum(cotas.values()), 2)
        self.assertEqual(cotas, {"b": 1, "a": 1, "c": 0})

    def test_alocar_maiores_restos_aceita_n_zero(self):
        cotas = alocar_maiores_restos({"a": 2, "b": 1}, 0, ["a", "b"])
        self.assertEqual(cotas, {"a": 0, "b": 0})

    def test_obter_pesos_condicionados_suporta_dependencia_multipla(self):
        spec = {
            "depende_de": ["persona_id", "weekend"],
            "pesos_condicionais": {
                "ana": {
                    "false": {"manha": 3, "tarde": 1},
                    "true": {"manha": 1, "tarde": 2},
                }
            },
        }

        self.assertEqual(
            obter_pesos_condicionados(spec, {"persona_id": "ana", "weekend": False}),
            {"manha": 3, "tarde": 1},
        )
        self.assertEqual(
            obter_pesos_condicionados(spec, {"persona_id": "ana", "weekend": True}),
            {"manha": 1, "tarde": 2},
        )

    def test_montar_prompt_usa_persona_e_missao_separadas(self):
        prompt = montar_prompt(
            {"identidade": "ID", "como_agir": "AGIR"},
            {"missao": "MISSAO"},
            "{identidade} :: {como_agir} :: {missao}",
        )
        self.assertEqual(prompt, "ID :: AGIR :: MISSAO")

    def test_calcular_plano_de_cotas_e_deterministico_para_multiplos_ns(self):
        for n in (1, 7, 90, 6000, 6001):
            config = copy.deepcopy(self.config)
            config["amostragem"]["n"] = n
            primeiro = calcular_plano_de_cotas(config)
            segundo = calcular_plano_de_cotas(config)

            self.assertEqual(sum(primeiro["dia_relativo"].values()), n)
            self.assertEqual(sum(primeiro["persona_id"].values()), n)
            self.assertEqual(primeiro, segundo)

    def test_pesos_brutos_de_dia_reproduzem_script_original(self):
        pesos = calcular_pesos_brutos_dia_relativo(self.config)

        self.assertAlmostEqual(pesos["d18"], 1.249525871218401)
        self.assertAlmostEqual(pesos["d36"], 0.8381284578044559)
        self.assertAlmostEqual(pesos["d47"], 1.2726300802655561)
        self.assertAlmostEqual(pesos["d62"], 0.5610492704143042)
        self.assertAlmostEqual(pesos["d73"], 1.2655854181090418)

    def test_cotas_temporais_para_6000_batem_com_v41_e_script_original(self):
        plano = calcular_plano_de_cotas(self.config)
        legacy_v41 = json.loads(LEGACY_V41_PATH.read_text(encoding="utf-8"))
        cotas_v41 = legacy_v41["amostragem"]["variaveis"]["dia_relativo"]["composicao_pesos"]["cotas_planejadas_n_6000"]
        script = runpy.run_path(str(ORIGINAL_SCRIPT_PATH), run_name="__test_original_generator__")
        _, cotas_script = script["gerar_cotas_dia_relativo_90d"]()

        self.assertEqual(plano["dia_relativo"], cotas_v41)
        self.assertEqual(plano["dia_relativo"], dict(cotas_script))
        self.assertEqual(plano["dia_relativo"]["d36"], 64)
        self.assertEqual(plano["dia_relativo"]["d62"], 42)

    def test_gerar_simulacoes_e_deterministico(self):
        config = copy.deepcopy(self.config)
        config["amostragem"]["n"] = 6001
        primeira_execucao = gerar_simulacoes(config)
        segunda_execucao = gerar_simulacoes(config)

        self.assertEqual(len(primeira_execucao), 6001)
        self.assertEqual(
            json.dumps(primeira_execucao, ensure_ascii=False, sort_keys=True),
            json.dumps(segunda_execucao, ensure_ascii=False, sort_keys=True),
        )

    def test_gerar_relatorio_auditoria_reflete_plano_e_observado(self):
        config = copy.deepcopy(self.config)
        config["amostragem"]["n"] = 7
        simulacoes = gerar_simulacoes(config)
        relatorio = gerar_relatorio_auditoria(config, simulacoes)

        self.assertEqual(relatorio["versao_schema"], "4.3")
        self.assertEqual(relatorio["n"], 7)
        self.assertIn("pesos_brutos_dia_relativo", relatorio)
        self.assertIn("pesos_percentuais_dia_relativo_derivados", relatorio)
        self.assertEqual(relatorio["cotas_calculadas"]["dia_relativo"], relatorio["contagens_observadas"]["dia_relativo"])
        self.assertTrue(all(relatorio["checks"].values()))
