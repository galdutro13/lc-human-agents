import json
from typing import Dict

class Persona:
    def __init__(self, json_str: str):
        self.dados_persona = json_str

    def print_dados(self):
        print(self.dados_persona)

    def dados_to_json(self) -> Dict:
        return json.loads(self.dados_persona)