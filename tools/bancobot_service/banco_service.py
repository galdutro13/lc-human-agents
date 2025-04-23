import secrets
import uvicorn
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, Optional, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

from source.tests.chatbot_test.banco import BancoBot


class MessageRequest(BaseModel):
    """Modelo para requisições de mensagem do cliente."""
    message: str
    session_id: Optional[str] = None
    timing_metadata: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    """Modelo para respostas às mensagens do cliente."""
    response: str
    session_id: str


app = FastAPI(title="BancoBot API",
              description="API para simulação de interações bancárias",
              version="1.0.0")

# Armazenar instâncias de BancoBot por sessão
bot_instances: Dict[str, BancoBot] = {}
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
        bot_instances[session_id] = await loop.run_in_executor(
            executor,
            lambda: BancoBot(think_exp=True)
        )
        print(f"Nova sessão criada: {session_id}")

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
    return {"sessions": list(bot_instances.keys()), "count": len(bot_instances)}


# Remover sessões inativas
@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Remove uma sessão específica do sistema."""
    if session_id in bot_instances:
        del bot_instances[session_id]
        return {"status": "success", "message": f"Sessão {session_id} removida"}
    raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")


@app.get("/health")
async def health_check():
    """Endpoint para verificação de saúde do serviço."""
    return {"status": "ok", "service": "BancoBot API"}


def start_server(host="0.0.0.0", port=8080):
    """Inicia o servidor FastAPI."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()