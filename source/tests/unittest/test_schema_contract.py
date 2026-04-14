import copy
import json
import unittest
from pathlib import Path

from source.simulation_config import ConfigValidationError, validar_config_v3


ROOT = Path(__file__).resolve().parents[3]
V3_PATH = ROOT / "config_v3.json"


class TestSchemaContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with V3_PATH.open("r", encoding="utf-8") as arquivo:
            cls.base_config = json.load(arquivo)

    def test_json_schema_v3_valido(self):
        validar_config_v3(self.base_config)

    def test_persona_id_orfao_falha_com_erro_claro(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["duracao"]["pesos_condicionais"]["persona_fantasma"] = {
            "rapida": 1,
            "media": 1,
            "lenta": 1,
        }

        with self.assertRaisesRegex(ConfigValidationError, "órfão"):
            validar_config_v3(config)

    def test_depende_de_invalido_falha(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["duracao"]["depende_de"] = "variavel_inexistente"

        with self.assertRaisesRegex(ConfigValidationError, "não está em dag_ordem"):
            validar_config_v3(config)

    def test_missing_default_quando_domino_pai_nao_coberto(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["duracao"]["pesos_condicionais"].pop("_default")

        with self.assertRaisesRegex(ConfigValidationError, "_default"):
            validar_config_v3(config)

    def test_ciclo_na_dag_falha(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["duracao"]["depende_de"] = "offset"

        with self.assertRaisesRegex(ConfigValidationError, "ciclo|ordem topológica"):
            validar_config_v3(config)

    def test_template_prompt_invalido_falha(self):
        config = copy.deepcopy(self.base_config)
        config["template_prompt"] = "{identidade} {missao}"

        with self.assertRaisesRegex(ConfigValidationError, "template_prompt"):
            validar_config_v3(config)

    def test_dag_invalida_por_duplicidade_ou_mismatch(self):
        config_duplicado = copy.deepcopy(self.base_config)
        config_duplicado["amostragem"]["dag_ordem"][0] = "duracao"
        with self.assertRaisesRegex(ConfigValidationError, "duplicadas|non-unique"):
            validar_config_v3(config_duplicado)

        config_mismatch = copy.deepcopy(self.base_config)
        config_mismatch["amostragem"]["dag_ordem"] = ["persona_id", "duracao", "offset", "fantasma"]
        with self.assertRaisesRegex(ConfigValidationError, "exatamente as variáveis"):
            validar_config_v3(config_mismatch)

    def test_schema_invalido_gera_erro_com_caminho(self):
        config = copy.deepcopy(self.base_config)
        config.pop("personas")

        with self.assertRaisesRegex(ConfigValidationError, "Configuração v3 inválida"):
            validar_config_v3(config)

    def test_n_seed_metodo_e_pesos_invalidos_falham(self):
        config_n = copy.deepcopy(self.base_config)
        config_n["amostragem"]["n"] = True
        with self.assertRaisesRegex(ConfigValidationError, "amostragem.n|'n'"):
            validar_config_v3(config_n)

        config_seed = copy.deepcopy(self.base_config)
        config_seed["amostragem"]["seed"] = False
        with self.assertRaisesRegex(ConfigValidationError, "amostragem.seed|'seed'"):
            validar_config_v3(config_seed)

        config_metodo = copy.deepcopy(self.base_config)
        config_metodo["amostragem"]["metodo"] = "rejeicao"
        with self.assertRaisesRegex(ConfigValidationError, "ancestral"):
            validar_config_v3(config_metodo)

        config_personas = copy.deepcopy(self.base_config)
        config_personas["amostragem"]["variaveis"]["persona_id"]["pesos"].pop("ana_beatriz_silva")
        with self.assertRaisesRegex(ConfigValidationError, "corresponder exatamente"):
            validar_config_v3(config_personas)

        config_pesos_vazios = copy.deepcopy(self.base_config)
        config_pesos_vazios["amostragem"]["variaveis"]["persona_id"]["pesos"] = {}
        with self.assertRaisesRegex(ConfigValidationError, "Configuração v3 inválida|não pode ser vazia"):
            validar_config_v3(config_pesos_vazios)

        config_peso_negativo = copy.deepcopy(self.base_config)
        config_peso_negativo["amostragem"]["variaveis"]["persona_id"]["pesos"]["ana_beatriz_silva"] = -1
        with self.assertRaisesRegex(ConfigValidationError, "Configuração v3 inválida|positivos"):
            validar_config_v3(config_peso_negativo)

    def test_chave_condicional_fora_do_dominio_falha(self):
        config = copy.deepcopy(self.base_config)
        config["amostragem"]["variaveis"]["weekend"]["pesos_condicionais"]["madrugada"] = {
            "true": 1,
            "false": 1,
        }

        with self.assertRaisesRegex(ConfigValidationError, "fora do domínio"):
            validar_config_v3(config)
