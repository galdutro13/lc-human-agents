import sqlite3
import csv
import json
import os


def inserir_cenarios(db_name: str, csv_path: str):
    """
    Lê um arquivo CSV (contendo cenario_id;dados_cenario) e insere cada linha na tabela 'Cenario'.
    Formato esperado do CSV:
        cenario_id;dados_cenario
        1;Começou a trabalhar como estagiário aos 18 anos...
        2;Aos 25, comprou seu primeiro apartamento...
    """

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')

        # Pular o cabeçalho (opcional, dependendo do CSV)
        # Se não quiser pular o cabeçalho, basta remover o next(reader) abaixo.
        header = next(reader, None)  # cenario_id;dados_cenario

        for row in reader:
            if len(row) != 2:
                print("Linha inválida no CSV: ", row)
                continue

            cenario_id_str, dados_cenario = row
            # Converter cenario_id para inteiro
            cenario_id = int(cenario_id_str)

            # Inserir no banco
            cursor.execute("""
                INSERT INTO Cenario (cenario_id, dados_cenario)
                VALUES (?, ?);
            """, (cenario_id, dados_cenario))

    conn.commit()
    conn.close()
    print(f"Cenários inseridos com sucesso a partir de '{csv_path}'.")


def inserir_personas(db_name: str, extracted_dir: str):
    """
    Lê todos os arquivos JSON na pasta 'extracted_dir' (ex: persona0.json, persona1.json, ...),
    extrai o 'persona_id' do nome do arquivo (ex.: 'persona0.json' -> 0) e
    armazena o conteúdo completo do JSON em 'dados_persona'.

    Observações:
      - O script assume que os arquivos têm nomes no padrão 'personaX.json',
        onde X é um número inteiro.
      - O conteúdo do JSON será lido como texto bruto e inserido em 'dados_persona'.
    """

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Verificar se o diretório existe
    if not os.path.isdir(extracted_dir):
        print(f"Pasta '{extracted_dir}' não encontrada.")
        return

    # Listar arquivos na pasta 'extracted_dir'
    for filename in os.listdir(extracted_dir):
        # Verifica se o arquivo começa com "persona" e termina com ".json"
        if filename.startswith("persona") and filename.endswith(".json"):
            # Extração do ID a partir do nome do arquivo
            # 'persona0.json' -> persona_id = 0
            # 'persona15.json' -> persona_id = 15, etc.
            try:
                # Remove 'persona' e '.json', deixando apenas o número
                numeric_part = filename.replace("persona", "").replace(".json", "")
                persona_id = int(numeric_part)
            except ValueError:
                print(f"Não foi possível extrair persona_id de '{filename}' — nome inconsistente.")
                continue

            # Ler o conteúdo do arquivo JSON como texto
            filepath = os.path.join(extracted_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                # Se quiser armazenar o JSON cru como string:
                json_content = f.read()

                # Se quiser processar para dicionário e re-salvar como texto formatado:
                # data_dict = json.loads(json_content)
                # json_content = json.dumps(data_dict, ensure_ascii=False)

            # Inserir ou atualizar no banco
            cursor.execute("""
                INSERT INTO Persona (persona_id, dados_persona)
                VALUES (?, ?);
            """, (persona_id, json_content))

    conn.commit()
    conn.close()
    print(f"Personas inseridas/atualizadas com sucesso a partir de '{extracted_dir}'.")


if __name__ == "__main__":
    db_name = "cenarios.db"

    # Exemplo de uso das funções
    inserir_cenarios(db_name, "data/Cenario.CSV")
    inserir_personas(db_name, "data/extracted/")
