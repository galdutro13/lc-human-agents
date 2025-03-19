import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import sqlite3
import io
import os
import pandas as pd
from pydantic import BaseModel

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langchain.schema import HumanMessage, AIMessage

from source.tests.chatbot_test import test_chatbot

class InteractionRequest(BaseModel):
    query: str


class InteractionResponse(BaseModel):
    success: bool

# Configure logging
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
app = FastAPI()

DATABASE_PATH = "checkpoints.db"

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@app.post("/new_interaction", response_model=InteractionResponse)
async def new_interaction(interaction: InteractionRequest):
    """
    Executes a new interaction based on the user's prompt.
    """
    try:
        # Run the chatbot function with the user query
        test_chatbot(interaction.query)
        return InteractionResponse(success=True)
    except Exception as exc:
        # Log the exception details internally
        logger.error("Failed to process new interaction", exc_info=exc)
        # Return a generic error message to the client
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/interactions")
def list_interactions():
    """
    Retorna uma lista de pares (thread_id, ts) em ordem cronológica de criação.

    Para cada thread_id encontrado na base, o procedimento é:
    1. Obter o primeiro registro do 'thread_id' (o que possui o menor checkpoint_id)
       para garantir que este registro seja o mais antigo e, portanto,
       reflita o timestamp inicial de criação.
    2. Decodificar o campo 'checkpoint' usando o JsonPlusSerializer.
    3. Extrair o campo 'ts' (timestamp) do objeto decodificado.
    4. Armazenar o par (thread_id, ts).
    5. Ordenar a lista resultante pelo ts, em ordem crescente (cronológica).
    6. Retornar a lista final de pares (thread_id, ts).

    O retorno é uma lista de dicionários, cada um com as chaves:
    - "thread_id": O identificador da thread.
    - "ts": O timestamp da criação dessa thread.
    """
    conn = get_db_connection()
    try:
        # Obtém todos os thread_ids distintos
        cursor = conn.execute("SELECT DISTINCT thread_id FROM checkpoints;")
        rows = cursor.fetchall()
        thread_ids = [row["thread_id"] for row in rows]

        thread_data = []
        for tid in thread_ids:
            # Seleciona o primeiro checkpoint da thread para obter seu timestamp inicial
            c = conn.execute("""
                SELECT checkpoint, type
                FROM checkpoints
                WHERE thread_id = ?
                ORDER BY checkpoint_id ASC
                LIMIT 1
            """, (tid,))
            first_row = c.fetchone()
            if not first_row:
                # Se não houver registro, passa para o próximo thread_id
                continue

            checkpoint_data = first_row["checkpoint"]
            record_type = first_row["type"]

            if checkpoint_data is None:
                # Se não houver dado do checkpoint, pula essa thread
                continue

            # Decodifica o checkpoint
            conversation = JsonPlusSerializer().loads_typed((record_type, checkpoint_data))

            # Extrai o timestamp (ts) do objeto.
            # Supondo que a chave 'ts' esteja disponível no nível superior do objeto:
            ts = conversation.get("ts", None)
            if ts is not None:
                thread_data.append({
                    "thread_id": tid,
                    "ts": ts
                })

        # Ordena a lista de threads pelo timestamp
        thread_data.sort(key=lambda x: x["ts"])

        return thread_data
    finally:
        conn.close()




@app.get("/interactions/{thread_id}")
def get_interaction(thread_id: str):
    """
    Obtém e retorna um objeto JSON simplificado com o histórico de mensagens
    para um determinado 'thread_id'.

    Esta função recupera a interação mais recente relacionada a um 'thread_id'
    específico a partir de um banco de dados. Em seguida, processa e converte
    os dados brutos do checkpoint em um formato simplificado de JSON, contendo
    apenas o array de mensagens com os campos 'content' e 'type'.

    Parâmetros
    ----------
    thread_id : str
        Identificador da interação (thread) cujo histórico de mensagens se
        deseja obter.

    Funcionalidade
    --------------
    1. Conexão com o banco de dados e seleção da última entrada (checkpoint)
       para o 'thread_id' especificado.
    2. Decodificação do checkpoint recuperado e conversão em um objeto
       Python-serializável.
    3. Extração do array de mensagens ('messages') do objeto obtido.
    4. Mapeamento de cada mensagem em um dicionário contendo apenas 'content'
       e 'type', descartando metadados e outros campos irrelevantes.
    5. Retorno de um objeto JSON no formato:
       {
         "messages": [
            {"content": ..., "type": ...},
            ...
         ]
       }

    Erros Possíveis
    ---------------
    - HTTPException(404): Se não houver nenhuma interação associada ao
      'thread_id' informado.
    - HTTPException(404): Se o checkpoint para a interação existindo for
      nulo ou vazio, indicando que não há histórico de mensagens válido.

    Retorno
    -------
    dict
        Um dicionário com a chave 'messages', cujo valor é uma lista de
        mensagens simplificadas (cada mensagem é um dicionário com os
        campos 'content' e 'type').

    Exemplo de Resposta
    -------------------
    {
      "messages": [
        {
          "content": "Olá! Como posso lhe ajudar?",
          "type": "human"
        },
        {
          "content": "Estou buscando informações sobre linhas de crédito...",
          "type": "ai"
        },
        ...
      ]
    }
    """
    conn = get_db_connection()
    try:
        # Recupera o último checkpoint do 'thread_id' especificado
        cursor = conn.execute("""
            SELECT checkpoint, type 
            FROM checkpoints
            WHERE thread_id = ?
            ORDER BY checkpoint_id DESC
            LIMIT 1
        """, (thread_id,))
        row = cursor.fetchone()
        if row is None:
            # Nenhuma interação encontrada para o thread_id
            raise HTTPException(status_code=404, detail="Interação não encontrada.")

        checkpoint_data = row["checkpoint"]
        record_type = row["type"]
        if checkpoint_data is None:
            # Histórico vazio ou inexistente, mesmo com o thread_id encontrado
            raise HTTPException(status_code=404, detail="Histórico não encontrado.")

        # Decodifica o checkpoint usando o serializador apropriado
        conversation = JsonPlusSerializer().loads_typed((record_type, checkpoint_data))

        # Extrai o array de mensagens do objeto carregado
        messages = conversation.get("channel_values", {}).get("messages", [])

        filtered_messages = []
        for msg in messages:
            # Extrai o conteúdo da mensagem
            msg_content = getattr(msg, "content", None)

            # Determina o tipo da mensagem
            # Supondo a utilização de classes como HumanMessage e AIMessage do LangChain:
            if isinstance(msg, HumanMessage):
                msg_type = "human"
            elif isinstance(msg, AIMessage):
                msg_type = "ai"
            else:
                # Caso seja necessário lidar com outros tipos de mensagem no futuro
                msg_type = "other"

            filtered_messages.append({
                "content": msg_content,
                "type": msg_type
            })

        # Retorna o objeto JSON simplificado conforme especificado
        return {"messages": filtered_messages}
    finally:
        # Garante o fechamento da conexão com o banco de dados
        conn.close()


@app.get("/interactions/{thread_id}/excel")
def export_interaction_excel(thread_id: str):
    """
    Gera e retorna um arquivo CSV contendo todas as mensagens
    (content e type) referentes à thread_id informada.
    """
    conn = get_db_connection()
    try:
        # Pega o último checkpoint do thread_id
        cursor = conn.execute("""
            SELECT checkpoint, type 
            FROM checkpoints
            WHERE thread_id = ?
            ORDER BY checkpoint_id DESC
            LIMIT 1
        """, (thread_id,))
        row = cursor.fetchone()

        if row is None or row["checkpoint"] is None:
            raise HTTPException(status_code=404, detail="Interação não encontrada ou sem conteúdo.")

        checkpoint_data = row["checkpoint"]
        record_type = row["type"]

        # Decodifica usando o serializador
        conversation = JsonPlusSerializer().loads_typed((record_type, checkpoint_data))
        messages = conversation.get("channel_values", {}).get("messages", [])

        # Monta uma lista de dicionários simples para criar o DataFrame
        data_for_df = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                msg_type = "human"
            elif isinstance(msg, AIMessage):
                msg_type = "ai"
            else:
                msg_type = "other"
            data_for_df.append({
                "type": msg_type,
                "content": getattr(msg, "content", "")
            })

        # Cria o DataFrame
        df = pd.DataFrame(data_for_df)

        # Gera o CSV em memória
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)

        # Retorna como StreamingResponse para download
        filename = f"conversa_{thread_id}.csv"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers=headers
        )

    finally:
        conn.close()