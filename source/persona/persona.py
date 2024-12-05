import json
from typing import Dict

class Persona:
    """
    Classe que representa uma pessoa com seus dados
    É usada para alimentar o GenerativeSystemPromptStrategy.
    """
    def __init__(self, json_str: str):
        self.dados_persona = json_str

    def print_dados(self):
        """
        Imprime os dados da persona
        :return:
        """
        print(self.dados_persona)

    def dados_to_json(self) -> Dict:
        """
        Retorna os dados da persona em formato de dicionário
        :return:
        """
        return json.loads(self.dados_persona)

    def get_dados_str(self):
        """
        Retorna os dados da persona em formato de string
        :return:
        """
        return self.dados_persona

