from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from datetime import datetime
import uvicorn
import os
import asyncio
from typing import Dict, Optional, List

from models import MessageRequest, MessageResponse, ChatConfig, ChatStatus
from source.tests.chatbot_test.usuario import UsuarioBot
from api_client import BancoApiClient

# Inicialização da aplicação FastAPI
app = FastAPI(
    title="UsuarioBot API",
    description="API para o serviço UsuarioBot",
    version="1.0.0"
)

# Armazenamento de instâncias ativas de UsuarioBot
active_bots: Dict[str, UsuarioBot] = {}

# Armazenamento do status das conversas
conversation_status: Dict[str, Dict] = {}

# Armazenamento de mapeamento entre threads do UsuarioBot e BancoBot
thread_mappings: Dict[str, str] = {}

# Configuração do cliente API para o serviço BancoBot
BANCO_API_URL = os.getenv("BANCO_API_URL", "http://localhost:8000")
banco_client = BancoApiClient(BANCO_API_URL)


def get_bot(thread_id: str) -> UsuarioBot:
    """
    Obtém uma instância de UsuarioBot para o thread_id fornecido.

    :param thread_id: ID único da conversa
    :return: Instância de UsuarioBot
    """
    if thread_id not in active_bots:
        raise HTTPException(status_code=404, detail=f"Conversa {thread_id} não encontrada")

    # Atualizar timestamp de última atividade
    conversation_status[thread_id]["last_activity"] = datetime.now().isoformat()
    return active_bots[thread_id]


@app.post("/message", response_model=MessageResponse)
async def process_message(request: MessageRequest):
    """
    Processa uma mensagem enviada ao UsuarioBot.

    :param request: Requisição contendo a mensagem
    :return: Resposta do UsuarioBot
    """
    if not request.thread_id:
        raise HTTPException(status_code=400, detail="thread_id é obrigatório")

    thread_id = request.thread_id

    try:
        bot = get_bot(thread_id)
        response = bot.process_query(request.message)

        # Incrementar contador de mensagens
        conversation_status[thread_id]["message_count"] += 1

        # Verificar se a conversa deve ser encerrada
        terminated = "quit" in response.lower()

        return MessageResponse(
            message=response,
            thread_id=thread_id,
            metadata={"service": "usuario", "timestamp": datetime.now().isoformat()},
            terminated=terminated
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar mensagem: {str(e)}")


@app.post("/session", response_model=ChatStatus)
async def create_session(config: ChatConfig):
    """
    Cria uma nova sessão de UsuarioBot.

    :param config: Configuração para o UsuarioBot
    :return: Status da nova sessão
    """
    thread_id = f"usuario_{os.urandom(3).hex()}"

    try:
        # Criar instância de UsuarioBot
        bot = UsuarioBot(
            think_exp=config.think_exp,
            system_message=config.system_message
        )

        # Substituir thread_id gerado pelo UsuarioBot
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
        raise HTTPException(status_code=500, detail=f"Erro ao criar sessão: {str(e)}")


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
            "message_count": status["message_count"],
            "banco_thread_id": thread_mappings.get(thread_id)
        }
    )


@app.post("/conversation/{thread_id}/start")
async def start_conversation(thread_id: str, initial_message: str = "Olá cliente Itaú! Como posso lhe ajudar?"):
    """
    Inicia uma conversa entre UsuarioBot e BancoBot.

    :param thread_id: ID da sessão UsuarioBot
    :param initial_message: Mensagem inicial do BancoBot
    :return: Resultado da conversa
    """
    try:
        # Verificar se a sessão existe
        if thread_id not in active_bots:
            raise HTTPException(status_code=404, detail=f"Sessão {thread_id} não encontrada")

        # Processar a mensagem inicial com o UsuarioBot
        usuario_response = active_bots[thread_id].process_query(initial_message)
        print(f"=== UsuarioBot Mensagem ===\n{usuario_response}")

        # Criar uma sessão no BancoBot
        banco_session = await banco_client.request("POST", "/bot", data={"think_exp": False})
        banco_thread_id = banco_session["thread_id"]

        # Armazenar o mapeamento entre os threads
        thread_mappings[thread_id] = banco_thread_id

        # Enviar a mensagem do UsuarioBot para o BancoBot
        banco_response = await banco_client.send_message(usuario_response, banco_thread_id)
        print(f"=== BancoBot Resposta ===\n{banco_response['message']}")

        # Verificar se a conversa deve ser encerrada
        if banco_response.get("terminated", False):
            return {"status": "terminated", "message": "Conversa encerrada pelo banco"}

        # Iniciar a conversa em segundo plano
        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            continue_conversation,
            usuario_thread_id=thread_id,
            banco_thread_id=banco_thread_id,
            banco_message=banco_response["message"]
        )

        return {
            "status": "started",
            "usuario_thread_id": thread_id,
            "banco_thread_id": banco_thread_id,
            "initial_response": usuario_response,
            "banco_response": banco_response["message"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar conversa: {str(e)}")


async def continue_conversation(usuario_thread_id: str, banco_thread_id: str, banco_message: str):
    """
    Continua a conversa entre UsuarioBot e BancoBot em segundo plano.

    :param usuario_thread_id: ID da sessão UsuarioBot
    :param banco_thread_id: ID da sessão BancoBot
    :param banco_message: Última mensagem do BancoBot
    """
    try:
        max_iterations = 10
        exit_command = "quit"

        for i in range(max_iterations):
            # Processar a mensagem do BancoBot com o UsuarioBot
            usuario_bot = active_bots[usuario_thread_id]
            usuario_response = usuario_bot.process_query(banco_message)
            print(f"=== UsuarioBot Mensagem ===\n{usuario_response}")

            # Verificar se a conversa deve ser encerrada pelo UsuarioBot
            if exit_command in usuario_response.lower():
                print("Encerrando a conversa pelo usuário.")
                break

            # Enviar a mensagem do UsuarioBot para o BancoBot
            banco_response = await banco_client.send_message(usuario_response, banco_thread_id)
            banco_message = banco_response["message"]
            print(f"=== BancoBot Resposta ===\n{banco_message}")

            # Verificar se a conversa deve ser encerrada pelo BancoBot
            if banco_message.lower() == exit_command or banco_response.get("terminated", False):
                print("Encerrando a conversa pelo banco.")
                break

            # Adicionar um pequeno atraso para simular a latência da conversa
            await asyncio.sleep(1)

    except Exception as e:
        print(f"Erro na conversa: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """Evento executado na inicialização do serviço."""
    print("Serviço UsuarioBot iniciado")


@app.on_event("shutdown")
async def shutdown_event():
    """Evento executado no encerramento do serviço."""
    print("Serviço UsuarioBot encerrado")


# Limpeza periódica de bots inativos
async def cleanup_inactive_bots():
    """Remove instâncias de UsuarioBot inativas após um período de inatividade."""
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
                if thread_id in thread_mappings:
                    del thread_mappings[thread_id]
                print(f"Bot removido por inatividade: {thread_id}")


@app.on_event("startup")
async def start_cleanup_task(background_tasks: BackgroundTasks):
    """Inicia a tarefa de limpeza em segundo plano."""
    background_tasks.add_task(cleanup_inactive_bots)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)