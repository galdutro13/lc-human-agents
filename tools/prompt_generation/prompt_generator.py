import os
import time

import google.generativeai as genai
import sqlite3

from tools.prompt_generation.get_generator_prompt import get_generator_prompt
from tools.prompt_generation.rate_limiter import RateLimiter
def gerar_prompts(persona, cenario, top_k=64, temperature=1.0):
    # Create the model
    generation_config = {
        "temperature": temperature,
        "top_p": 0.95,
        "top_k": top_k,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-thinking-exp-1219",
        generation_config=generation_config,
    )

    response = model.generate_content(get_generator_prompt(persona, cenario))
    return response.candidates[0].content.parts[1].text


def listar_missoes_com_detalhes(db_name: str):
    """
    Retorna (ou imprime) uma lista de dicionários, em que cada dicionário representa
    uma missão, já carregando os valores de dados_persona e dados_cenario referenciados.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Realiza um JOIN para carregar tudo em uma única query:
    cursor.execute("""
        SELECT
            m.missao_id,
            m.persona_id,
            m.cenario_id,
            p.dados_persona,
            c.dados_cenario
        FROM Missao m
        JOIN Persona p ON m.persona_id = p.persona_id
        JOIN Cenario c ON m.cenario_id = c.cenario_id
        LEFT JOIN Template_prompt t ON m.missao_id = t.missao_id
        WHERE t.missao_id IS NULL

    """)

    rows = cursor.fetchall()
    conn.close()

    # Transformar o resultado em uma lista de dicionários (opcional, mas organizado)
    missoes = []
    for row in rows:
        missoes.append({
            "missao_id": row[0],
            "persona_id": row[1],
            "cenario_id": row[2],
            "dados_persona": row[3],
            "dados_cenario": row[4]
        })

    return missoes

def inserir_prompt(db_name: str, missao_id: int, prompt_text: str) -> int | bool:
    """
    Insere um 'prompt' na tabela Template_prompt do banco 'db_name',
    desde que:
      - prompt_text inicie com "Você é "
      - prompt_text contenha as substrings "[[ como agir ]]" e "[[ missão ]]"

    Parâmetros:
      db_name    : Nome (ou caminho) do arquivo SQLite.
      missao_id  : ID da missão à qual o prompt se refere.
      prompt_text: Conteúdo textual do prompt a ser inserido.

    Retorno:
      - Retorna o ID (AUTOINCREMENT) gerado para o prompt,
        ou None se não houve inserção por não atender aos critérios.
    """

    # Verifica se o prompt inicia com "Você é "
    if not prompt_text.startswith("Você é "):
        print("O prompt não inicia com 'Você é '. Inserção cancelada.")
        return False

    # Verifica se contém as substrings obrigatórias
    if "[[ como agir ]]" not in prompt_text or "[[ missão ]]" not in prompt_text:
        print("O prompt não contém as substrings '[[ como agir ]]' e/ou '[[ missão ]]'. Inserção cancelada.")
        return False

    if "quit" not in prompt_text:
        print("O prompt não contém a substring 'quit'. Inserção cancelada.")
        return False

    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # Insere o prompt na tabela
        cursor.execute("""
            INSERT INTO Template_prompt (missao_id, prompt)
            VALUES (?, ?);
        """, (missao_id, prompt_text))

        conn.commit()
        new_prompt_id = cursor.lastrowid
        conn.close()

        print(f"Prompt inserido com sucesso. prompt_id = {new_prompt_id}")
        return new_prompt_id

    except sqlite3.Error as e:
        print(f"Erro ao inserir prompt: {e}")
        return False

if __name__ == "__main__":
    db_name = "cenarios.db"
    resultado = listar_missoes_com_detalhes(db_name)

    # Define que queremos no máximo 10 chamadas em 60 segundos
    rate_limiter = RateLimiter(max_calls=10, window_seconds=60)

    # Exemplo: imprimir cada missão
    for missao in resultado:
        temperature: float = 1.0
        top_k: int = 64
        factor: int = 2
        # Aguarda até que haja "vaga" para realizar nova chamada
        rate_limiter.wait_for_slot()

        prompt = gerar_prompts(missao["dados_persona"], missao["dados_cenario"])
        while not inserir_prompt(db_name, missao["missao_id"], prompt):
            top_k = top_k // factor
            temperature = temperature * 0.75

            # Se top_k for menor que 8, não faz sentido continuar tentando
            if top_k < 8:
                break

            rate_limiter.wait_for_slot()
            prompt = gerar_prompts(missao["dados_persona"],
                                   missao["dados_cenario"],
                                   top_k=top_k,
                                   temperature=temperature)
