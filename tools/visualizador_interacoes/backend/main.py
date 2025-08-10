import logging
import json
import zipfile
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import sqlite3
import io
import os
import pandas as pd
import threading
from datetime import datetime
from pydantic import BaseModel
from pathlib import Path
import glob

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langchain.schema import HumanMessage, AIMessage

# Import UsuarioBot directly from the decoupled structure
from source.tests.chatbot_test.usuario import UsuarioBot


class InteractionRequest(BaseModel):
    query: str


class InteractionResponse(BaseModel):
    success: bool


class ThreadIdMapping(BaseModel):
    mappings: dict[str, str]


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

# Set debug level for specific debugging
# Uncomment the following line to enable debug logging for RAG logs extraction
# logger.setLevel(logging.DEBUG)

app = FastAPI()

DATABASE_PATH = "checkpoints.db"
RAG_LOGS_PATH = "rag_logs"  # Path to RAG logs directory

# IMPORTANT: Thread ID Mapping Configuration
# If there's a consistent mismatch between checkpoint thread_ids and RAG log thread_ids,
# you can define a mapping here. For example:
# THREAD_ID_MAPPING = {
#     "checkpoint_thread_id": "rag_log_thread_id",
#     "0296d8a620475903": "8f49061abfe8ca53",
#     # Add more mappings as needed
# }
THREAD_ID_MAPPING = {}  # Empty by default


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def find_rag_log_by_persona(persona_id: str, thread_id: str) -> str:
    """
    Try to find RAG log file by persona_id if thread_id doesn't match.

    Args:
        persona_id: The persona ID to look for
        thread_id: The thread ID (for reference)

    Returns:
        Path to the log file if found, None otherwise
    """
    try:
        # Pattern: rag_logs_{persona_id}_{any_thread_id}_{timestamp}.zip
        # Note: persona_id might be in format "persona_X"
        pattern = os.path.join(RAG_LOGS_PATH, f"rag_logs_{persona_id}_*.zip")
        files = glob.glob(pattern)

        if files:
            # Return the most recent file
            return max(files, key=os.path.getctime)

        return None
    except Exception as e:
        logger.error(f"Error finding RAG log by persona: {e}")
        return None


def find_rag_log_by_timestamp(conversation_ts: str, tolerance_minutes: int = 30) -> str:
    """
    Try to find RAG log file by timestamp proximity.

    Args:
        conversation_ts: The conversation timestamp
        tolerance_minutes: Time tolerance in minutes

    Returns:
        Path to the log file if found within tolerance, None otherwise
    """
    try:
        if not conversation_ts:
            return None

        # Parse conversation timestamp
        conv_time = datetime.fromisoformat(conversation_ts.replace('Z', '+00:00'))

        # Get all RAG log files
        rag_files = glob.glob(os.path.join(RAG_LOGS_PATH, "rag_logs_*.zip"))

        best_match = None
        min_diff = float('inf')

        for file_path in rag_files:
            filename = os.path.basename(file_path)
            # Extract timestamp from filename (last part before .zip)
            # Pattern: rag_logs_persona_X_{thread_id}_{YYYYMMDD_HHMMSS}.zip
            parts = filename.replace('.zip', '').split('_')
            if len(parts) >= 6:
                try:
                    date_str = parts[-2]  # YYYYMMDD
                    time_str = parts[-1]  # HHMMSS
                    file_time = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")

                    # Calculate time difference
                    diff = abs((file_time - conv_time.replace(tzinfo=None)).total_seconds() / 60)

                    if diff < tolerance_minutes and diff < min_diff:
                        min_diff = diff
                        best_match = file_path
                except:
                    continue

        if best_match:
            logger.info(f"Found RAG log by timestamp proximity: {best_match} (diff: {min_diff:.1f} minutes)")

        return best_match
    except Exception as e:
        logger.error(f"Error finding RAG log by timestamp: {e}")
        return None


def extract_datasources_from_rag_logs(thread_id: str, message_index: int, persona_id: str = None,
                                      conversation_ts: str = None) -> list:
    """
    Extract unique datasources used for a specific message from RAG logs.

    IMPORTANT: There might be a mismatch between thread_ids in the checkpoints database
    and thread_ids in the RAG log filenames. This can happen if:
    1. The RAG logs are from a different run than the checkpoints
    2. Thread IDs are transformed between systems
    3. The logs have been manually moved or renamed

    To debug this issue, use the /debug/rag_logs_mapping endpoint.

    Args:
        thread_id: The thread ID to look for
        message_index: The message index (1-based) to extract datasources for
        persona_id: Optional persona ID to use as fallback
        conversation_ts: Optional conversation timestamp for fallback

    Returns:
        List of unique datasources used, or ["none"] if fallback was used
    """
    try:
        # Check if RAG logs directory exists
        if not os.path.exists(RAG_LOGS_PATH):
            logger.warning(f"RAG logs directory does not exist: {RAG_LOGS_PATH}")
            return []

        # Check if there's a manual mapping for this thread_id
        mapped_thread_id = THREAD_ID_MAPPING.get(thread_id, thread_id)
        if mapped_thread_id != thread_id:
            logger.info(f"Using mapped thread_id: {mapped_thread_id} for original: {thread_id}")

        # Find the RAG log ZIP file for this thread
        # Pattern: rag_logs_persona_X_{thread_id}_{timestamp}.zip
        log_pattern = os.path.join(RAG_LOGS_PATH, f"rag_logs_persona_*_{mapped_thread_id}_*.zip")
        log_files = glob.glob(log_pattern)

        # If not found by thread_id and persona_id is provided, try finding by persona
        if not log_files and persona_id:
            log_file = find_rag_log_by_persona(persona_id, thread_id)
            if log_file:
                log_files = [log_file]
                logger.info(f"Found RAG log by persona_id: {persona_id} for thread_id: {thread_id}")

        # If still not found, try by timestamp
        if not log_files and conversation_ts:
            log_file = find_rag_log_by_timestamp(conversation_ts)
            if log_file:
                log_files = [log_file]
                logger.info(f"Found RAG log by timestamp for thread_id: {thread_id}")

        if not log_files:
            # Log available files for debugging
            available_files = os.listdir(RAG_LOGS_PATH)
            logger.debug(f"Available RAG log files: {available_files}")
            logger.warning(
                f"No RAG log files found for thread_id: {thread_id} (mapped: {mapped_thread_id}) with pattern: {log_pattern}")
            return []

        # Use the most recent log file if multiple exist
        log_file = max(log_files, key=os.path.getctime)
        logger.debug(f"Found RAG log file: {log_file} for thread_id: {thread_id}")

        # Extract and parse the session metadata
        with zipfile.ZipFile(log_file, 'r') as zf:
            # Find the metadata file
            metadata_files = [f for f in zf.namelist() if f.startswith("session_metadata_")]
            if not metadata_files:
                logger.warning(f"No metadata file found in {log_file}")
                return []

            # Read the metadata
            with zf.open(metadata_files[0]) as mf:
                metadata = json.load(mf)

        # Find the logs for the specific message
        datasources = set()
        fallback_used = False

        # Look for the message with the given index
        for msg in metadata.get("messages", []):
            if msg.get("index") == message_index:
                # Parse logs for this message
                for log_entry in msg.get("logs", []):
                    # Look for routing decisions
                    if log_entry.get("message") == "Routing decision":
                        datasource = log_entry.get("data", {}).get("selected_datasource")
                        if datasource:
                            datasources.add(datasource)

                    # Check if fallback was used
                    if "Generating fallback response" in log_entry.get("message", ""):
                        fallback_used = True

                    # Also check for fallback in function names
                    if log_entry.get("message", "").startswith("Starting FallbackFunction"):
                        fallback_used = True

                break

        # If fallback was used and no datasources were selected, return ["none"]
        if fallback_used and not datasources:
            return ["none"]

        # Return sorted list of unique datasources
        return sorted(list(datasources))

    except Exception as e:
        logger.error(f"Error extracting datasources from RAG logs: {e}")
        return []


def run_chatbot(prompt: str, api_url: str = "http://localhost:8080", max_iterations: int = 10) -> bool:
    """
    Runs a chatbot interaction with the provided prompt.
    Creates and runs a UsuarioBot instance that communicates with the bancobot_service.

    Args:
        prompt: The prompt to use for the UsuarioBot
        api_url: URL of the bancobot service
        max_iterations: Maximum number of iterations for the conversation

    Returns:
        True if the interaction was successful, False otherwise
    """
    try:
        # Create and run a UsuarioBot configured to use the bancobot_service
        usuario_bot = UsuarioBot(
            think_exp=False,
            system_message=prompt,
            api_url=api_url
        )

        # Start the interaction with an initial greeting
        usuario_bot.run(
            initial_query="Olá cliente X! Como posso lhe ajudar?",
            max_iterations=max_iterations
        )
        return True
    except Exception as e:
        logger.error(f"Error in run_chatbot: {e}")
        return False


@app.post("/new_interaction", response_model=InteractionResponse)
async def new_interaction(interaction: InteractionRequest):
    """
    Executes a new interaction based on the user's prompt.
    Uses decoupled UsuarioBot that connects to bancobot_service.
    """
    try:
        # Run the chatbot in a separate thread to avoid blocking the API
        thread = threading.Thread(
            target=run_chatbot,
            args=(interaction.query,)
        )
        thread.daemon = True
        thread.start()

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


@app.post("/config/thread_id_mapping")
def update_thread_id_mapping(mapping_request: ThreadIdMapping):
    """
    Update the thread ID mapping configuration.

    Example request body:
    {
        "mappings": {
            "0296d8a620475903": "8f49061abfe8ca53",
            "05b1cb0ec39314b9": "0d99eb38b87b7165"
        }
    }
    """
    global THREAD_ID_MAPPING
    THREAD_ID_MAPPING.update(mapping_request.mappings)
    logger.info(f"Updated thread ID mapping with {len(mapping_request.mappings)} entries")
    return {"success": True, "updated_mappings": len(mapping_request.mappings),
            "total_mappings": len(THREAD_ID_MAPPING)}


@app.get("/config/thread_id_mapping")
def get_thread_id_mapping():
    """
    Get the current thread ID mapping configuration.
    """
    return {
        "mappings": THREAD_ID_MAPPING,
        "total_mappings": len(THREAD_ID_MAPPING)
    }


@app.get("/debug/rag_logs_mapping")
def debug_rag_logs():
    """
    Debug endpoint to show the mapping between thread_ids and RAG log files.
    """
    mapping = debug_rag_logs_mapping()

    # Also get thread_ids from the database
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT DISTINCT thread_id FROM checkpoints;")
        db_thread_ids = [row["thread_id"] for row in cursor.fetchall()]

        return {
            "rag_logs_mapping": mapping,
            "database_thread_ids": db_thread_ids,
            "rag_logs_path": RAG_LOGS_PATH,
            "rag_logs_exist": os.path.exists(RAG_LOGS_PATH)
        }
    finally:
        conn.close()


@app.get("/interactions/raw/{thread_id}")
def get_interaction_raw(thread_id: str):
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
        # Retorna o objeto JSON completo
        return conversation
    finally:
        # Garante o fechamento da conexão com o banco de dados
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


@app.get("/interactions/{thread_id}/csv")
def export_interaction_csv(thread_id: str):
    """
    Gera e retorna um arquivo CSV contendo todas as mensagens
    (content, type, simulated_timestamp e elapsed_time) referentes à thread_id informada.
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
        persona_id = conversation.get("channel_values", {}).get("persona_id", None)

        # Monta uma lista de dicionários para criar o DataFrame
        data_for_df = []
        for msg in messages:
            # Determina o tipo de mensagem (invertido conforme explicado)
            if isinstance(msg, HumanMessage):
                msg_type = "ai"  # Mensagens do banco têm type="human" mas representam o chatbot
            elif isinstance(msg, AIMessage):
                msg_type = "human"  # Mensagens do simulador têm type="ai" mas representam o usuário
            else:
                msg_type = "other"

            # Extrai informações de timing
            timing_metadata = getattr(msg, "additional_kwargs", {}).get("timing_metadata", {})

            # Determina simulated_timestamp e elapsed_time baseado no tipo real
            if isinstance(msg, HumanMessage):  # Mensagem do banco
                simulated_timestamp = timing_metadata.get("banco_generation_timestamp", "")
                elapsed_time = timing_metadata.get("banco_generation_elapsed_time", 0)
            elif isinstance(msg, AIMessage):  # Mensagem do simulador
                simulated_timestamp = timing_metadata.get("simulated_timestamp", "")
                # Soma thinking_time + typing_time + break_time
                thinking_time = timing_metadata.get("thinking_time", 0)
                typing_time = timing_metadata.get("typing_time", 0)
                break_time = timing_metadata.get("break_time", 0)
                elapsed_time = thinking_time + typing_time + break_time
            else:
                simulated_timestamp = ""
                elapsed_time = 0

            data_for_df.append({
                "type": msg_type,
                "content": getattr(msg, "content", ""),
                "simulated_timestamp": simulated_timestamp,
                "elapsed_time": elapsed_time
            })

        # Cria o DataFrame
        df = pd.DataFrame(data_for_df)

        # Gera o CSV em memória
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)

        # Retorna como StreamingResponse para download
        filename = f"conversa_{persona_id}_{thread_id}.csv"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers=headers
        )

    finally:
        conn.close()


@app.get("/interactions/export/all_csv_zip")
def export_all_interactions_zip():
    """
    Exporta todas as interações em arquivos CSV separados e retorna um ZIP.
    Cada CSV corresponde a uma thread_id e inclui informações de timestamp.
    """
    conn = get_db_connection()
    try:
        # Busca todos os thread_ids distintos
        cursor = conn.execute("SELECT DISTINCT thread_id FROM checkpoints;")
        rows = cursor.fetchall()
        thread_ids = [row["thread_id"] for row in rows]

        # Cria um ZIP em memória
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for tid in thread_ids:
                # Busca o último checkpoint da thread
                c = conn.execute("""
                                 SELECT checkpoint, type
                                 FROM checkpoints
                                 WHERE thread_id = ?
                                 ORDER BY checkpoint_id DESC
                                 LIMIT 1
                                 """, (tid,))
                row = c.fetchone()
                if not row or not row["checkpoint"]:
                    continue

                checkpoint_data = row["checkpoint"]
                record_type = row["type"]
                conversation = JsonPlusSerializer().loads_typed((record_type, checkpoint_data))
                messages = conversation.get("channel_values", {}).get("messages", [])
                persona_id = conversation.get("channel_values", {}).get("persona_id", "unknown")

                # Monta lista de mensagens para o DataFrame
                data_for_df = []
                for msg in messages:
                    # Determina o tipo de mensagem (invertido conforme explicado)
                    if isinstance(msg, HumanMessage):
                        msg_type = "ai"  # Mensagens do banco
                    elif isinstance(msg, AIMessage):
                        msg_type = "human"  # Mensagens do simulador
                    else:
                        msg_type = "other"

                    # Extrai informações de timing
                    timing_metadata = getattr(msg, "additional_kwargs", {}).get("timing_metadata", {})

                    # Determina simulated_timestamp e elapsed_time baseado no tipo real
                    if isinstance(msg, HumanMessage):  # Mensagem do banco
                        simulated_timestamp = timing_metadata.get("banco_generation_timestamp", "")
                        elapsed_time = timing_metadata.get("banco_generation_elapsed_time", 0)
                    elif isinstance(msg, AIMessage):  # Mensagem do simulador
                        simulated_timestamp = timing_metadata.get("simulated_timestamp", "")
                        # Soma thinking_time + typing_time + break_time
                        thinking_time = timing_metadata.get("thinking_time", 0)
                        typing_time = timing_metadata.get("typing_time", 0)
                        break_time = timing_metadata.get("break_time", 0)
                        elapsed_time = thinking_time + typing_time + break_time
                    else:
                        simulated_timestamp = ""
                        elapsed_time = 0

                    data_for_df.append({
                        "type": msg_type,
                        "content": getattr(msg, "content", ""),
                        "simulated_timestamp": simulated_timestamp,
                        "elapsed_time": elapsed_time
                    })

                # Cria o DataFrame e salva em CSV em memória
                df = pd.DataFrame(data_for_df)
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_bytes = csv_buffer.getvalue().encode("utf-8")

                # Nome do arquivo CSV
                filename = f"conversa_{persona_id}_{tid}.csv"
                zip_file.writestr(filename, csv_bytes)

        zip_buffer.seek(0)
        headers = {"Content-Disposition": "attachment; filename=interacoes.zip"}
        return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)
    finally:
        conn.close()


@app.get("/interactions/export/all_json_zip")
def export_all_interactions_json_zip():
    """
    Exporta todas as interações em arquivos JSON separados e retorna um ZIP.
    Cada JSON corresponde a uma thread_id e inclui informações de timestamp e datasources do RAG.
    """
    conn = get_db_connection()
    try:
        # Busca todos os thread_ids distintos
        cursor = conn.execute("SELECT DISTINCT thread_id FROM checkpoints;")
        rows = cursor.fetchall()
        thread_ids = [row["thread_id"] for row in rows]

        # Cria um ZIP em memória
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Também cria um índice geral de todas as conversas
            all_conversations_index = []

            for tid in thread_ids:
                # Busca o último checkpoint da thread
                c = conn.execute("""
                                 SELECT checkpoint, type
                                 FROM checkpoints
                                 WHERE thread_id = ?
                                 ORDER BY checkpoint_id DESC
                                 LIMIT 1
                                 """, (tid,))
                row = c.fetchone()
                if not row or not row["checkpoint"]:
                    continue

                checkpoint_data = row["checkpoint"]
                record_type = row["type"]
                conversation = JsonPlusSerializer().loads_typed((record_type, checkpoint_data))
                messages = conversation.get("channel_values", {}).get("messages", [])
                persona_id = conversation.get("channel_values", {}).get("persona_id", "unknown")

                # Extrai timestamp da conversa
                conversation_ts = conversation.get("ts", None)

                # Monta lista de mensagens para o JSON
                messages_data = []
                message_counter = 0  # Contador para rastrear a posição da mensagem no RAG

                # IMPORTANTE: O mapeamento dos datasources considera que:
                # - A primeira mensagem AI (index 0) é um placeholder que não passa pelo RAG
                # - O primeiro datasource do RAG corresponde à segunda mensagem AI (index 2)
                # - E assim por diante: RAG message 1 -> AI message index 2,
                #                      RAG message 2 -> AI message index 4, etc.

                for msg_index, msg in enumerate(messages):
                    # Determina o tipo de mensagem (invertido conforme explicado)
                    if isinstance(msg, HumanMessage):
                        msg_type = "ai"  # Mensagens do banco têm type="human" mas representam o chatbot
                        # Incrementa o contador apenas para mensagens AI que não sejam o placeholder inicial
                        if msg_index > 0:
                            message_counter += 1
                    elif isinstance(msg, AIMessage):
                        msg_type = "human"  # Mensagens do simulador têm type="ai" mas representam o usuário
                    else:
                        msg_type = "other"

                    # Extrai informações de timing
                    timing_metadata = getattr(msg, "additional_kwargs", {}).get("timing_metadata", {})

                    # Determina simulated_timestamp e elapsed_time baseado no tipo real
                    if isinstance(msg, HumanMessage):  # Mensagem do banco
                        simulated_timestamp = timing_metadata.get("banco_generation_timestamp", "")
                        elapsed_time = timing_metadata.get("banco_generation_elapsed_time", 0)
                    elif isinstance(msg, AIMessage):  # Mensagem do simulador
                        simulated_timestamp = timing_metadata.get("simulated_timestamp", "")
                        # Soma thinking_time + typing_time + break_time
                        thinking_time = timing_metadata.get("thinking_time", 0)
                        typing_time = timing_metadata.get("typing_time", 0)
                        break_time = timing_metadata.get("break_time", 0)
                        elapsed_time = thinking_time + typing_time + break_time
                    else:
                        simulated_timestamp = ""
                        elapsed_time = 0

                    # Cria objeto da mensagem com metadados adicionais
                    message_obj = {
                        "index": msg_index,
                        "type": msg_type,
                        "content": getattr(msg, "content", ""),
                        "simulated_timestamp": simulated_timestamp,
                        "elapsed_time": elapsed_time,
                        "timing_metadata": timing_metadata  # Inclui todos os metadados de timing
                    }

                    # Adiciona ID da mensagem se disponível
                    if hasattr(msg, "id") and msg.id:
                        message_obj["message_id"] = msg.id

                    # Adiciona datasources do RAG apenas para mensagens do tipo "ai" (respostas do banco)
                    if msg_type == "ai":
                        if msg_index == 0:
                            # A primeira mensagem AI é um placeholder que não passa pelo RAG
                            message_obj["rag_datasources"] = []
                        else:
                            # Mensagens AI subsequentes têm datasources do RAG
                            datasources = extract_datasources_from_rag_logs(tid, message_counter, persona_id,
                                                                            conversation_ts)
                            message_obj["rag_datasources"] = datasources

                    messages_data.append(message_obj)

                # Cria estrutura completa da conversa
                conversation_data = {
                    "thread_id": tid,
                    "persona_id": persona_id,
                    "conversation_timestamp": conversation_ts,
                    "total_messages": len(messages_data),
                    "messages": messages_data,
                    "metadata": {
                        "export_timestamp": datetime.now().isoformat(),
                        "export_version": "2.0"  # Updated version to indicate RAG datasources support
                    }
                }

                # Adiciona informações resumidas ao índice geral
                all_conversations_index.append({
                    "thread_id": tid,
                    "persona_id": persona_id,
                    "conversation_timestamp": conversation_ts,
                    "total_messages": len(messages_data),
                    "filename": f"conversa_{persona_id}_{tid}.json"
                })

                # Converte para JSON com formatação legível
                json_content = json.dumps(conversation_data, indent=2, ensure_ascii=False)
                json_bytes = json_content.encode("utf-8")

                # Nome do arquivo JSON
                filename = f"conversa_{persona_id}_{tid}.json"
                zip_file.writestr(filename, json_bytes)

            # Adiciona arquivo de índice ao ZIP
            if all_conversations_index:
                index_data = {
                    "export_metadata": {
                        "export_timestamp": datetime.now().isoformat(),
                        "total_conversations": len(all_conversations_index),
                        "export_version": "2.0"  # Updated version
                    },
                    "conversations": all_conversations_index
                }
                index_json = json.dumps(index_data, indent=2, ensure_ascii=False)
                zip_file.writestr("index.json", index_json.encode("utf-8"))

        zip_buffer.seek(0)
        headers = {"Content-Disposition": "attachment; filename=interacoes_json.zip"}
        return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)
    finally:
        conn.close()


@app.get("/interactions/{thread_id}/json")
def export_interaction_json(thread_id: str):
    """
    Gera e retorna um arquivo JSON contendo todas as mensagens e metadados
    completos referentes à thread_id informada, incluindo os datasources do RAG.
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
        persona_id = conversation.get("channel_values", {}).get("persona_id", None)
        conversation_ts = conversation.get("ts", None)

        # Monta estrutura completa das mensagens
        messages_data = []
        message_counter = 0  # Contador para rastrear a posição da mensagem no RAG

        # IMPORTANTE: O mapeamento dos datasources considera que:
        # - A primeira mensagem AI (index 0) é um placeholder que não passa pelo RAG
        # - O primeiro datasource do RAG corresponde à segunda mensagem AI (index 2)
        # - E assim por diante: RAG message 1 -> AI message index 2,
        #                      RAG message 2 -> AI message index 4, etc.

        for msg_index, msg in enumerate(messages):
            # Determina o tipo de mensagem (invertido conforme explicado)
            if isinstance(msg, HumanMessage):
                msg_type = "ai"  # Mensagens do banco têm type="human" mas representam o chatbot
                # Incrementa o contador apenas para mensagens AI que não sejam o placeholder inicial
                if msg_index > 0:
                    message_counter += 1
            elif isinstance(msg, AIMessage):
                msg_type = "human"  # Mensagens do simulador têm type="ai" mas representam o usuário
            else:
                msg_type = "other"

            # Extrai informações de timing
            timing_metadata = getattr(msg, "additional_kwargs", {}).get("timing_metadata", {})

            # Determina simulated_timestamp e elapsed_time baseado no tipo real
            if isinstance(msg, HumanMessage):  # Mensagem do banco
                simulated_timestamp = timing_metadata.get("banco_generation_timestamp", "")
                elapsed_time = timing_metadata.get("banco_generation_elapsed_time", 0)
            elif isinstance(msg, AIMessage):  # Mensagem do simulador
                simulated_timestamp = timing_metadata.get("simulated_timestamp", "")
                # Soma thinking_time + typing_time + break_time
                thinking_time = timing_metadata.get("thinking_time", 0)
                typing_time = timing_metadata.get("typing_time", 0)
                break_time = timing_metadata.get("break_time", 0)
                elapsed_time = thinking_time + typing_time + break_time
            else:
                simulated_timestamp = ""
                elapsed_time = 0

            # Cria objeto completo da mensagem
            message_obj = {
                "index": msg_index,
                "type": msg_type,
                "content": getattr(msg, "content", ""),
                "simulated_timestamp": simulated_timestamp,
                "elapsed_time": elapsed_time,
                "timing_metadata": timing_metadata
            }

            # Adiciona ID da mensagem se disponível
            if hasattr(msg, "id") and msg.id:
                message_obj["message_id"] = msg.id

            # Adiciona datasources do RAG apenas para mensagens do tipo "ai" (respostas do banco)
            if msg_type == "ai":
                if msg_index == 0:
                    # A primeira mensagem AI é um placeholder que não passa pelo RAG
                    message_obj["rag_datasources"] = []
                else:
                    # Mensagens AI subsequentes têm datasources do RAG
                    datasources = extract_datasources_from_rag_logs(thread_id, message_counter, persona_id,
                                                                    conversation_ts)
                    message_obj["rag_datasources"] = datasources

            messages_data.append(message_obj)

        # Estrutura completa para exportação
        export_data = {
            "thread_id": thread_id,
            "persona_id": persona_id,
            "conversation_timestamp": conversation_ts,
            "total_messages": len(messages_data),
            "messages": messages_data,
            "metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "export_version": "2.0"  # Updated version to indicate RAG datasources support
            }
        }

        # Gera o JSON
        json_content = json.dumps(export_data, indent=2, ensure_ascii=False)

        # Retorna como StreamingResponse para download
        filename = f"conversa_{persona_id}_{thread_id}.json"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return StreamingResponse(
            io.StringIO(json_content),
            media_type="application/json",
            headers=headers
        )

    finally:
        conn.close()