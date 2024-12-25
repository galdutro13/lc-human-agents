import csv
import json
from typing import List, Dict


class CSVtoJSONConverter:
    """Converte registros CSV em strings JSON."""

    def __init__(self, csv_file_path: str):
        """
        Inicializa o conversor com o caminho para um arquivo CSV.

        :param csv_file_path: Caminho para o arquivo CSV a ser convertido.
        """
        self.csv_file_path = csv_file_path

    def convert_entire_file(self) -> List[str]:
        """
        Converte todos os registros no arquivo CSV para uma lista de strings JSON.

        :return: Lista de strings JSON representando cada registro CSV.
        """
        records = self._read_csv_file()
        json_strings = [json.dumps(record, ensure_ascii=False) for record in records]
        return json_strings

    def convert_single_record(self, record_number: int) -> str:
        """
        Converte um único registro do arquivo CSV para uma string JSON.

        :param record_number: O índice do registro a ser convertido (começando em 0).
        :return: String JSON representando o registro CSV especificado.
        :raises IndexError: Se o número do registro estiver fora do intervalo.
        """
        records = self._read_csv_file()
        if 0 <= record_number < len(records):
            return json.dumps(records[record_number], ensure_ascii=False)
        else:
            raise IndexError("Número de registro fora do intervalo.")

    def _read_csv_file(self) -> List[Dict[str, str]]:
        """
        Lê o arquivo CSV e retorna uma lista de registros como dicionários.

        :return: Lista de dicionários representando registros CSV.
        :raises FileNotFoundError: Se o arquivo CSV não existir.
        :raises csv.Error: Se ocorrer um erro ao ler o arquivo CSV.
        """
        try:
            with open(self.csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                headers = reader.fieldnames
                records = []
                for row in reader:
                    if None in row.values():
                        raise ValueError("Linha com campos faltantes detectada.")
                    records.append(row)
            return records
        except FileNotFoundError as e:
            print(f"Erro: O arquivo {self.csv_file_path} não foi encontrado.")
            raise e
        except csv.Error as e:
            print("Erro: Ocorreu um erro ao ler o arquivo CSV.")
            raise e
