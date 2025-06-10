# tools/bancobot_service/banco_service.py (MODIFIED)
import secrets
import uvicorn
import os
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from source.tests.chatbot_test.banco import BancoBot


class MessageRequest(BaseModel):
    """Modelo para requisições de mensagem do cliente."""
    message: str
    session_id: Optional[str] = None
    timing_metadata: Optional[Dict[str, Any]] = None
    persona_id: Optional[str] = None  # Added persona_id support


class MessageResponse(BaseModel):
    """Modelo para respostas às mensagens do cliente."""
    response: str
    session_id: str


app = FastAPI(title="BancoBot API",
              description="API para simulação de interações bancárias",
              version="1.0.0")

# Armazenar instâncias de BancoBot por sessão
bot_instances: Dict[str, BancoBot] = {}
# Armazenar persona_id por sessão
session_personas: Dict[str, str] = {}
# Executor para operações de inicialização que são CPU-bound
executor = ThreadPoolExecutor(max_workers=4)


@app.post("/api/message", response_model=MessageResponse)
async def process_message(request: MessageRequest = Body(...)):
    """
    Processa uma mensagem de um usuário.
    Cria uma nova sessão se necessário ou utiliza uma sessão existente.
    Agora suporta metadados de temporização para simular comportamento temporal do usuário.
    """
    # Se não tiver session_id, cria um novo
    session_id = request.session_id or secrets.token_hex(8)

    # Store persona_id if provided
    if request.persona_id:
        session_personas[session_id] = request.persona_id

    # Log timing metadata if present
    if request.timing_metadata:
        print(f"[Session {session_id}] Received timing metadata:")
        print(f"  - Timestamp simulado: {request.timing_metadata.get('simulated_timestamp', 'N/A')}")
        print(f"  - Tempo de reflexão: {request.timing_metadata.get('thinking_time', 0):.2f} segundos")
        print(f"  - Tempo de digitação: {request.timing_metadata.get('typing_time', 0):.2f} segundos")
        print(f"  - Tempo de pausa: {request.timing_metadata.get('break_time', 0):.2f} segundos")

    # Verifica se já existe um bot para essa sessão
    if session_id not in bot_instances:
        # Cria uma nova instância de BancoBot para a sessão
        # Usamos o executor para não bloquear o loop de eventos, pois a inicialização é CPU-bound
        loop = asyncio.get_event_loop()

        # Get persona_id for this session
        persona_id = session_personas.get(session_id, request.persona_id)

        # Create bot with persona_id for logging
        bot_instances[session_id] = await loop.run_in_executor(
            executor,
            lambda: BancoBot(think_exp=False, persona_id=persona_id, thread_id=session_id)
        )
        print(f"Nova sessão criada: {session_id} (persona: {persona_id})")

    # Processa a mensagem usando o bot da sessão de forma assíncrona
    try:
        response = await bot_instances[session_id].aprocess_message(request.message)
        return MessageResponse(response=response, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar mensagem: {str(e)}")


# Funcionalidade administrativa para listar sessões ativas
@app.get("/api/sessions")
async def list_sessions():
    """Lista todas as sessões ativas no serviço."""
    sessions_info = []
    for session_id, bot in bot_instances.items():
        sessions_info.append({
            "session_id": session_id,
            "persona_id": session_personas.get(session_id, "unknown")
        })
    return {"sessions": sessions_info, "count": len(bot_instances)}


# Remover sessões inativas
@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Remove uma sessão específica do sistema e gera logs se disponíveis."""
    if session_id in bot_instances:
        bot = bot_instances[session_id]

        # Generate logs before deleting
        log_path = None
        try:
            if hasattr(bot, 'generate_logs_zip'):
                log_path = bot.generate_logs_zip()
                if log_path:
                    print(f"[Session {session_id}] RAG logs saved to: {log_path}")
        except Exception as e:
            print(f"[Session {session_id}] Error generating logs: {e}")

        # Close the bot
        if hasattr(bot, 'close'):
            bot.close()

        # Remove from instances
        del bot_instances[session_id]

        # Remove persona mapping
        if session_id in session_personas:
            del session_personas[session_id]

        return {
            "status": "success",
            "message": f"Sessão {session_id} removida",
            "log_path": log_path
        }
    raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")


@app.get("/api/sessions/{session_id}/logs")
async def get_session_logs(session_id: str):
    """Obtém o arquivo ZIP de logs de uma sessão específica."""
    if session_id not in bot_instances:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")

    bot = bot_instances[session_id]

    # Generate logs
    try:
        if hasattr(bot, 'generate_logs_zip'):
            log_path = bot.generate_logs_zip()
            if log_path and os.path.exists(log_path):
                return FileResponse(
                    path=log_path,
                    media_type='application/zip',
                    filename=os.path.basename(log_path)
                )
            else:
                raise HTTPException(status_code=404, detail="Arquivo de logs não encontrado")
        else:
            raise HTTPException(status_code=501, detail="Bot não suporta geração de logs")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar logs: {str(e)}")


@app.get("/health")
async def health_check():
    """Endpoint para verificação de saúde do serviço."""
    return {"status": "ok", "service": "BancoBot API"}


# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Gera logs para todas as sessões ativas antes de encerrar."""
    print("Gerando logs para todas as sessões ativas...")

    for session_id, bot in bot_instances.items():
        try:
            if hasattr(bot, 'generate_logs_zip'):
                log_path = bot.generate_logs_zip()
                if log_path:
                    print(f"[Session {session_id}] Logs salvos em: {log_path}")

            if hasattr(bot, 'close'):
                bot.close()
        except Exception as e:
            print(f"[Session {session_id}] Erro ao gerar logs: {e}")

    print("Shutdown completo.")


def start_server(host="0.0.0.0", port=8080):
    """Inicia o servidor FastAPI."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()