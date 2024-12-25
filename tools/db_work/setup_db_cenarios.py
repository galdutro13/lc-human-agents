import sqlite3

# Script SQL de criação das tabelas (pode ser armazenado em uma variável ou em um arquivo .sql)
sql_script = """
PRAGMA foreign_keys = ON;

-- 1) Tabela Persona
CREATE TABLE IF NOT EXISTS Persona (
    persona_id     INTEGER      PRIMARY KEY,
    dados_persona  TEXT
);

-- 2) Tabela Cenario
CREATE TABLE IF NOT EXISTS Cenario (
    cenario_id     INTEGER      PRIMARY KEY,
    dados_cenario  TEXT
);

-- 3) Tabela Missao
CREATE TABLE IF NOT EXISTS Missao (
    missao_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_id  INTEGER NOT NULL,
    cenario_id  INTEGER NOT NULL,
    FOREIGN KEY (persona_id) REFERENCES Persona(persona_id),
    FOREIGN KEY (cenario_id) REFERENCES Cenario(cenario_id),
    UNIQUE (persona_id, cenario_id)
);

-- 4) Tabela Template_prompt
CREATE TABLE IF NOT EXISTS Template_prompt (
    prompt_id  INTEGER      PRIMARY KEY AUTOINCREMENT,
    missao_id  INTEGER      NOT NULL,
    prompt     TEXT         NOT NULL,

    FOREIGN KEY (missao_id) REFERENCES Missao(missao_id)
);
"""


def criar_banco_de_dados(db_name: str):
    # Cria (ou conecta a) um banco de dados SQLite local com o nome especificado.
    # Em seguida, executa o script de criação das tabelas.

    # 1. Conecta ao arquivo .db (se o arquivo não existir, ele será criado)
    conn = sqlite3.connect(db_name)

    # 2. Cria um cursor para executar comandos SQL
    cursor = conn.cursor()

    # 3. Executa o script de criação das tabelas
    cursor.executescript(sql_script)

    # 4. Confirma (commit) as alterações
    conn.commit()

    # 5. Fecha a conexão
    conn.close()
    print(f"Banco de dados '{db_name}' criado (ou verificado) com sucesso.")


# Exemplo de uso
if __name__ == "__main__":
    criar_banco_de_dados("cenarios.db")
