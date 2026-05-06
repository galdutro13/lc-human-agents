import copy
import unittest
from pathlib import Path

from source.simulation_config import ConfigValidationError, carregar_config_v44, validar_config_v44


ROOT = Path(__file__).resolve().parents[3]
V44_PATH = ROOT / "config_v4_4.json"


class TestSchemaContractV44(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_config = carregar_config_v44(V44_PATH)

    def test_config_v44_valido(self):
        validar_config_v44(self.base_config)

    def test_rejeita_default(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["ritmo"]["pesos_condicionais"]["ana_beatriz_silva"]["_default"] = 1

        with self.assertRaisesRegex(ConfigValidationError, "_default"):
            validar_config_v44(config)

    def test_rejeita_dependencia_inexistente(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["offset"]["depende_de"] = ["persona_id", "variavel_fantasma"]

        with self.assertRaisesRegex(ConfigValidationError, "não está em dag_ordem"):
            validar_config_v44(config)

    def test_rejeita_missao_inexistente_na_matriz(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["missao_id"]["missoes_elegiveis_por_persona"]["ana_beatriz_silva"]["H"].append(
            "m99_inexistente"
        )

        with self.assertRaisesRegex(ConfigValidationError, "missões inexistentes"):
            validar_config_v44(config)

    def test_rejeita_calendario_materializado(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["dia_relativo"]["calendario"] = {
            "d01": {
                "dia_indice": 1,
                "mes_relativo": 1,
                "semana_relativa": 1,
                "dia_da_semana": "segunda",
                "dia_do_mes_sintetico": 1,
                "weekend": False,
            }
        }

        with self.assertRaisesRegex(ConfigValidationError, "Configuração v4.4 inválida"):
            validar_config_v44(config)

    def test_rejeita_peso_final_divergente_da_formula(self):
        config = copy.deepcopy(self.base_config)
        composicao = config["amostragem"]["variaveis"]["persona_id"]["composicao_pesos"]
        composicao["peso_final"]["ana_beatriz_silva"] = 999

        with self.assertRaisesRegex(ConfigValidationError, "peso_final.*ana_beatriz_silva"):
            validar_config_v44(config)

    def test_rejeita_duracao_temporal_diferente_de_90(self):
        config = copy.deepcopy(self.base_config)
        config["janela_temporal"]["duracao"] = 91

        with self.assertRaisesRegex(ConfigValidationError, "Configuração v4.4 inválida|90 dias"):
            validar_config_v44(config)

    def test_rejeita_dia_inicio_invalido(self):
        config = copy.deepcopy(self.base_config)
        config["janela_temporal"]["dia_inicio"] = "feriado"

        with self.assertRaisesRegex(ConfigValidationError, "Configuração v4.4 inválida|dia_inicio"):
            validar_config_v44(config)

    def test_rejeita_dias_por_mes_sintetico_diferente_de_30(self):
        config = copy.deepcopy(self.base_config)
        config["janela_temporal"]["dias_por_mes_sintetico"] = 31

        with self.assertRaisesRegex(ConfigValidationError, "Configuração v4.4 inválida|dias_por_mes_sintetico"):
            validar_config_v44(config)

    def test_rejeita_calendario_sintetico_false(self):
        config = copy.deepcopy(self.base_config)
        config["janela_temporal"]["calendario_sintetico"] = False

        with self.assertRaisesRegex(ConfigValidationError, "Configuração v4.4 inválida|calendario_sintetico"):
            validar_config_v44(config)

    def test_rejeita_snapshot_fixo_de_cotas(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["persona_id"]["composicao_pesos"]["cotas_planejadas_n_6000"] = {
            "ana_beatriz_silva": 1
        }

        with self.assertRaisesRegex(ConfigValidationError, "Configuração v4.4 inválida"):
            validar_config_v44(config)

    def test_rejeita_pesos_explicitos_de_dia_relativo(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["dia_relativo"]["composicao_pesos"]["pesos"] = {
            "d01": 1
        }

        with self.assertRaisesRegex(ConfigValidationError, "Configuração v4.4 inválida"):
            validar_config_v44(config)

    def test_rejeita_fator_temporal_alterado(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["dia_relativo"]["composicao_pesos"]["fatores_dia_semana"]["segunda"] = 1.07

        with self.assertRaisesRegex(ConfigValidationError, "fatores_dia_semana"):
            validar_config_v44(config)
