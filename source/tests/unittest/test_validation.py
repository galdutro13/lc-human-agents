import copy
import unittest
from pathlib import Path

from source.simulation_config import (
    calcular_plano_de_cotas,
    carregar_config_v42,
    gerar_simulacoes,
    validar_simulacoes_geradas,
)
from source.simulation_config.errors import ConfigValidationError


ROOT = Path(__file__).resolve().parents[3]
V42_PATH = ROOT / "config_v4_2.json"


class TestValidationV42(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = carregar_config_v42(V42_PATH)
        cls.simulacoes = gerar_simulacoes(cls.config)

    def test_validar_simulacoes_geradas_passa(self):
        validar_simulacoes_geradas(self.config, self.simulacoes)

    def test_cotas_derivadas_de_dia_e_persona_batem(self):
        plano = calcular_plano_de_cotas(self.config)
        contagem_dias = {chave: 0 for chave in plano["dia_relativo"].keys()}
        contagem_personas = {chave: 0 for chave in plano["persona_id"].keys()}

        for simulacao in self.simulacoes:
            contagem_dias[simulacao["dia_relativo"]] += 1
            contagem_personas[simulacao["persona_id"]] += 1

        self.assertEqual(contagem_dias, plano["dia_relativo"])
        self.assertEqual(contagem_personas, plano["persona_id"])

    def test_weekend_e_compatibilidade_sao_respeitados(self):
        calendario = self.config["amostragem"]["variaveis"]["dia_relativo"]["calendario"]
        elegiveis = self.config["amostragem"]["variaveis"]["missao_id"]["missoes_elegiveis_por_persona"]

        for simulacao in self.simulacoes:
            self.assertEqual(
                simulacao["weekend"],
                calendario[simulacao["dia_relativo"]]["weekend"],
            )
            permitidas = set(elegiveis[simulacao["persona_id"]]["H"]) | set(
                elegiveis[simulacao["persona_id"]]["M"]
            )
            self.assertIn(simulacao["missao_id"], permitidas)

    def test_validacao_rejeita_registro_invalido(self):
        simulacoes = copy.deepcopy(self.simulacoes)
        simulacoes[0]["missao_id"] = "m99_inexistente"

        with self.assertRaisesRegex(ConfigValidationError, "missao_id inexistente"):
            validar_simulacoes_geradas(self.config, simulacoes)

    def test_validacao_funciona_com_n_pequeno(self):
        config = copy.deepcopy(self.config)
        config["amostragem"]["n"] = 7
        simulacoes = gerar_simulacoes(config)
        validar_simulacoes_geradas(config, simulacoes)
