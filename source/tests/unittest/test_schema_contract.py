import copy
import unittest
from pathlib import Path

from source.simulation_config import ConfigValidationError, carregar_config_v42, validar_config_v42


ROOT = Path(__file__).resolve().parents[3]
V42_PATH = ROOT / "config_v4_2.json"


class TestSchemaContractV42(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_config = carregar_config_v42(V42_PATH)

    def test_config_v42_valido(self):
        validar_config_v42(self.base_config)

    def test_rejeita_default(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["ritmo"]["pesos_condicionais"]["ana_beatriz_silva"]["_default"] = 1

        with self.assertRaisesRegex(ConfigValidationError, "_default"):
            validar_config_v42(config)

    def test_rejeita_dependencia_inexistente(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["offset"]["depende_de"] = ["persona_id", "variavel_fantasma"]

        with self.assertRaisesRegex(ConfigValidationError, "não está em dag_ordem"):
            validar_config_v42(config)

    def test_rejeita_missao_inexistente_na_matriz(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["missao_id"]["missoes_elegiveis_por_persona"]["ana_beatriz_silva"]["H"].append(
            "m99_inexistente"
        )

        with self.assertRaisesRegex(ConfigValidationError, "missões inexistentes"):
            validar_config_v42(config)

    def test_rejeita_calendario_inconsistente(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["dia_relativo"]["calendario"]["d01"]["weekend"] = True

        with self.assertRaisesRegex(ConfigValidationError, "Calendário com weekend inconsistente"):
            validar_config_v42(config)

    def test_rejeita_peso_final_divergente_da_formula(self):
        config = copy.deepcopy(self.base_config)
        composicao = config["amostragem"]["variaveis"]["persona_id"]["composicao_pesos"]
        composicao["peso_final"]["ana_beatriz_silva"] = 999

        with self.assertRaisesRegex(ConfigValidationError, "peso_final.*ana_beatriz_silva"):
            validar_config_v42(config)

    def test_rejeita_dia_da_semana_inconsistente_com_indice(self):
        config = copy.deepcopy(self.base_config)
        calendario = config["amostragem"]["variaveis"]["dia_relativo"]["calendario"]
        calendario["d01"]["dia_da_semana"] = "domingo"
        calendario["d01"]["weekend"] = True

        with self.assertRaisesRegex(ConfigValidationError, "dia_indice/dia_da_semana"):
            validar_config_v42(config)

    def test_rejeita_dia_indice_duplicado_ou_faltante(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["dia_relativo"]["calendario"]["d02"]["dia_indice"] = 1

        with self.assertRaisesRegex(ConfigValidationError, "dia_indice inconsistente"):
            validar_config_v42(config)

    def test_rejeita_snapshot_fixo_de_cotas(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["persona_id"]["composicao_pesos"]["cotas_planejadas_n_6000"] = {
            "ana_beatriz_silva": 1
        }

        with self.assertRaisesRegex(ConfigValidationError, "Configuração v4.2 inválida"):
            validar_config_v42(config)
