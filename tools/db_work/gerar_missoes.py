import sqlite3


def gerar_missoes(db_name: str):
    """
    Gera todas as combinações possíveis entre personas e cenários,
    inserindo-as na tabela Missao.

    Pré-requisitos:
      - Tabelas Persona(campo persona_id) e Cenario(campo cenario_id) já populadas.
      - Tabela Missao(missao_id, persona_id, cenario_id) com missao_id como PK (autoincrement).
    """

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Obtém todos os persona_id disponíveis
    cursor.execute("SELECT persona_id FROM Persona;")
    lista_personas = cursor.fetchall()  # Ex.: [(1,), (2,), (3,), ...]

    # Obtém todos os cenario_id disponíveis
    cursor.execute("SELECT cenario_id FROM Cenario;")
    lista_cenarios = cursor.fetchall()  # Ex.: [(1,), (2,), (3,), ...]

    # Para cada persona_id, combinamos com cada cenario_id
    for (persona_id,) in lista_personas:
        for (cenario_id,) in lista_cenarios:
            cursor.execute("""
                INSERT OR IGNORE INTO Missao (persona_id, cenario_id) 
                VALUES (?, ?);

            """, (persona_id, cenario_id))

    conn.commit()
    conn.close()
    print(f"Todas as combinações Persona x Cenario foram inseridas em 'Missao' no banco {db_name}.")


if __name__ == "__main__":
    db_name = "cenarios.db"
    gerar_missoes(db_name)
