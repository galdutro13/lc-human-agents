from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from datetime import datetime
import uvicorn
import os
from typing import Dict, Optional, List
import asyncio

from models import MessageRequest, MessageResponse, ChatConfig, ChatStatus
from source.tests.chatbot_test.banco import BancoBot

# Inicialização da aplicação FastAPI
app = FastAPI(
    title="BancoBot API",
    description="API para o serviço BancoBot",
    version="1.0.0"
)

# Armazenamento de instâncias ativas de BancoBot
active_bots: Dict[str, BancoBot] = {}

# Armazenamento do status das conversas
conversation_status: Dict[str, Dict] = {}


def get_bot(thread_id: str) -> BancoBot:
    """
    Obtém uma instância de BancoBot para o thread_id fornecido.
    Cria uma nova instância se não existir.

    :param thread_id: ID único da conversa
    :return: Instância de BancoBot
    """
    if thread_id not in active_bots:
        bot = BancoBot(think_exp=False)
        # Substituir thread_id gerado pelo BancoBot pelo thread_id fornecido
        bot.thread_id = thread_id
        bot.config = {"configurable": {"thread_id": thread_id}}
        active_bots[thread_id] = bot

        # Inicializar o status da conversa
        conversation_status[thread_id] = {
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "message_count": 0
        }

    # Atualizar timestamp de última atividade
    conversation_status[thread_id]["last_activity"] = datetime.now().isoformat()
    return active_bots[thread_id]


@app.post("/message", response_model=MessageResponse)
async def process_message(request: MessageRequest):
    """
    Processa uma mensagem enviada ao BancoBot.

    :param request: Requisição contendo a mensagem
    :return: Resposta do BancoBot
    """
    thread_id = request.thread_id or f"banco_{os.urandom(3).hex()}"

    try:
        bot = get_bot(thread_id)
        response = bot.process_query(request.message)

        # Incrementar contador de mensagens
        conversation_status[thread_id]["message_count"] += 1

        # Verificar se a conversa deve ser encerrada
        terminated = response.lower() == "quit"

        return MessageResponse(
            message=response,
            thread_id=thread_id,
            metadata={"service": "banco", "timestamp": datetime.now().isoformat()},
            terminated=terminated
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar mensagem: {str(e)}")


@app.get("/status/{thread_id}", response_model=ChatStatus)
async def get_chat_status(thread_id: str):
    """
    Obtém o status de uma conversa.

    :param thread_id: ID da conversa
    :return: Status da conversa
    """
    if thread_id not in conversation_status:
        raise HTTPException(status_code=404, detail=f"Conversa {thread_id} não encontrada")

    status = conversation_status[thread_id]
    return ChatStatus(
        thread_id=thread_id,
        is_active=status["is_active"],
        last_activity=status["last_activity"],
        metadata={
            "created_at": status["created_at"],
            "message_count": status["message_count"]
        }
    )


@app.post("/bot", response_model=ChatStatus)
async def create_bot(config: ChatConfig):
    """
    Cria uma nova instância de BancoBot com a configuração fornecida.

    :param config: Configuração para o BancoBot
    :return: Status da nova instância
    """
    thread_id = f"banco_{os.urandom(3).hex()}"

    try:
        bot = BancoBot(think_exp=config.think_exp)

        # Substituir thread_id gerado pelo BancoBot
        bot.thread_id = thread_id
        bot.config = {"configurable": {"thread_id": thread_id}}

        active_bots[thread_id] = bot

        # Inicializar o status da conversa
        conversation_status[thread_id] = {
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "message_count": 0
        }

        return ChatStatus(
            thread_id=thread_id,
            is_active=True,
            last_activity=conversation_status[thread_id]["last_activity"],
            metadata={"created_at": conversation_status[thread_id]["created_at"]}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar BancoBot: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """Evento executado na inicialização do serviço."""
    print("Serviço BancoBot iniciado")


@app.on_event("shutdown")
async def shutdown_event():
    """Evento executado no encerramento do serviço."""
    print("Serviço BancoBot encerrado")


# Limpeza periódica de bots inativos
async def cleanup_inactive_bots():
    """Remove instâncias de BancoBot inativas após um período de inatividade."""
    while True:
        await asyncio.sleep(3600)  # Verificar a cada hora
        current_time = datetime.now()

        for thread_id, status in list(conversation_status.items()):
            last_activity = datetime.fromisoformat(status["last_activity"])
            hours_inactive = (current_time - last_activity).total_seconds() / 3600

            # Remover bots inativos por mais de 24 horas
            if hours_inactive > 24:
                if thread_id in active_bots:
                    del active_bots[thread_id]
                del conversation_status[thread_id]
                print(f"Bot removido por inatividade: {thread_id}")


@app.on_event("startup")
async def start_cleanup_task(background_tasks: BackgroundTasks):
    """Inicia a tarefa de limpeza em segundo plano."""
    background_tasks.add_task(cleanup_inactive_bots)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)