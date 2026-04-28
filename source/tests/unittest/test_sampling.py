import copy
import json
import unittest
from pathlib import Path

from source.simulation_config import (
    alocar_maiores_restos,
    calcular_plano_de_cotas,
    carregar_config_v42,
    gerar_relatorio_auditoria,
    gerar_simulacoes,
    montar_prompt,
    obter_pesos_condicionados,
)


ROOT = Path(__file__).resolve().parents[3]
V42_PATH = ROOT / "config_v4_2.json"


class TestSamplingV42(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = carregar_config_v42(V42_PATH)

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

        self.assertEqual(relatorio["versao_schema"], "4.2")
        self.assertEqual(relatorio["n"], 7)
        self.assertEqual(relatorio["cotas_calculadas"]["dia_relativo"], relatorio["contagens_observadas"]["dia_relativo"])
        self.assertTrue(all(relatorio["checks"].values()))
