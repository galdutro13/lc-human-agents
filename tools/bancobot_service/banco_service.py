# tools/bancobot_service/banco_service.py (FIXED - NO MEMORY LEAKS)
import secrets
import uvicorn
import os
from fastapi import FastAPI, HTTPException, Body, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timedelta
import weakref
import gc

from source.tests.chatbot_test.banco import BancoBot


# Note: If you've updated the original BancoBot to support register_atexit parameter,
# you can use: BancoBot(think_exp=False, persona_id=persona_id, thread_id=session_id, register_atexit=False)
# Otherwise, use the BancoBotNoAtExit class defined below


class MessageRequest(BaseModel):
    """Modelo para requisições de mensagem do cliente."""
    message: str
    session_id: Optional[str] = None
    timing_metadata: Optional[Dict[str, Any]] = None
    persona_id: Optional[str] = None


class MessageResponse(BaseModel):
    """Modelo para respostas às mensagens do cliente."""
    response: str
    session_id: str


# Configuration for session management
MAX_SESSIONS = 1000  # Maximum number of concurrent sessions
SESSION_TIMEOUT_MINUTES = 30  # Session timeout in minutes
CLEANUP_INTERVAL_SECONDS = 300  # Run cleanup every 5 minutes


class SessionManager:
    """Manages bot sessions with automatic cleanup and memory management."""

    def __init__(self, max_sessions: int = MAX_SESSIONS,
                 timeout_minutes: int = SESSION_TIMEOUT_MINUTES):
        self.bot_instances: Dict[str, BancoBot] = {}
        self.session_personas: Dict[str, str] = {}
        self.session_last_access: Dict[str, datetime] = {}
        self.max_sessions = max_sessions
        self.timeout_delta = timedelta(minutes=timeout_minutes)
        self.lock = asyncio.Lock()
        # Use weak references to track bot cleanup
        self._finalizer_refs = weakref.WeakValueDictionary()

    async def get_or_create_session(self, session_id: Optional[str],
                                    persona_id: Optional[str],
                                    executor: ThreadPoolExecutor) -> tuple[str, BancoBot]:
        """Get existing session or create new one with proper cleanup."""
        async with self.lock:
            # Generate session ID if not provided
            if not session_id:
                session_id = secrets.token_hex(8)

            # Update last access time
            self.session_last_access[session_id] = datetime.now()

            # Return existing bot if available
            if session_id in self.bot_instances:
                return session_id, self.bot_instances[session_id]

            # Check if we've reached max sessions
            if len(self.bot_instances) >= self.max_sessions:
                # Remove oldest session
                oldest_session = min(self.session_last_access.items(),
                                     key=lambda x: x[1])[0]
                await self.remove_session(oldest_session)

            # Create new bot instance
            loop = asyncio.get_event_loop()
            bot = await loop.run_in_executor(
                executor,
                self._create_bot_with_cleanup,
                persona_id,
                session_id
            )

            # Store session data
            self.bot_instances[session_id] = bot
            if persona_id:
                self.session_personas[session_id] = persona_id

            print(f"Nova sessão criada: {session_id} (persona: {persona_id})")
            return session_id, bot

    def _create_bot_with_cleanup(self, persona_id: Optional[str],
                                 session_id: str) -> BancoBot:
        """Create bot instance with proper cleanup handling."""
        # Create bot with proper cleanup handling
        # Note: We'll need to use the original BancoBot with register_atexit=False
        # or implement BancoBotNoAtExit as shown below
        bot = BancoBotNoAtExit(think_exp=False, persona_id=persona_id,
                               thread_id=session_id)

        # Track with weak reference for debugging
        self._finalizer_refs[session_id] = bot

        return bot

    async def remove_session(self, session_id: str) -> Optional[str]:
        """Remove session and properly clean up resources."""
        async with self.lock:
            if session_id not in self.bot_instances:
                return None

            bot = self.bot_instances[session_id]
            log_path = None

            try:
                # Generate logs before cleanup
                if hasattr(bot, 'generate_logs_zip'):
                    log_path = bot.generate_logs_zip()
                    if log_path:
                        print(f"[Session {session_id}] RAG logs saved to: {log_path}")

                # Properly close the bot and all its resources
                if hasattr(bot, 'close'):
                    bot.close()

                # Additional cleanup for RAG system
                if hasattr(bot, 'app') and bot.app:
                    if hasattr(bot.app, 'close'):
                        bot.app.close()
                    # Clear references to heavy objects
                    bot.app = None

                # Clear the model and prompt references
                bot.model = None
                bot.prompt = None

            except Exception as e:
                print(f"[Session {session_id}] Error during cleanup: {e}")

            # Remove from tracking dictionaries
            del self.bot_instances[session_id]
            self.session_personas.pop(session_id, None)
            self.session_last_access.pop(session_id, None)

            # Force garbage collection for large objects
            gc.collect()

            return log_path

    async def cleanup_expired_sessions(self) -> int:
        """Remove sessions that have exceeded the timeout period."""
        now = datetime.now()
        expired_sessions = []

        async with self.lock:
            for session_id, last_access in self.session_last_access.items():
                if now - last_access > self.timeout_delta:
                    expired_sessions.append(session_id)

        # Remove expired sessions outside the lock to avoid holding it too long
        removed_count = 0
        for session_id in expired_sessions:
            await self.remove_session(session_id)
            removed_count += 1
            print(f"[Cleanup] Removed expired session: {session_id}")

        return removed_count

    async def get_session_info(self) -> Dict[str, Any]:
        """Get information about all active sessions."""
        async with self.lock:
            sessions_info = []
            now = datetime.now()

            for session_id, bot in self.bot_instances.items():
                last_access = self.session_last_access.get(session_id, now)
                idle_time = (now - last_access).total_seconds()

                sessions_info.append({
                    "session_id": session_id,
                    "persona_id": self.session_personas.get(session_id, "unknown"),
                    "idle_seconds": idle_time,
                    "expires_in_seconds": max(0, (self.timeout_delta.total_seconds() - idle_time))
                })

            return {
                "sessions": sessions_info,
                "count": len(self.bot_instances),
                "max_sessions": self.max_sessions,
                "timeout_minutes": self.timeout_delta.total_seconds() / 60
            }


# Custom BancoBot that doesn't use atexit
class BancoBotNoAtExit(BancoBot):
    """BancoBot without atexit registration to prevent memory leaks."""

    def __init__(self, think_exp: bool, persona_id: Optional[str] = None,
                 thread_id: Optional[str] = None):
        # Call parent init but we'll override the atexit behavior
        super().__init__(think_exp=think_exp, persona_id=persona_id,
                         thread_id=thread_id)

    def _cleanup_logging(self):
        """Override to prevent atexit registration."""
        # This method is called by parent, but we don't register with atexit
        pass


app = FastAPI(title="BancoBot API",
              description="API para simulação de interações bancárias com gerenciamento de memória",
              version="2.0.0")

# Create session manager
session_manager = SessionManager()

# Create executor with proper lifecycle management
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="BancoBot-")

# Background task for periodic cleanup
cleanup_task = None


@app.on_event("startup")
async def startup_event():
    """Initialize the cleanup task on startup."""
    global cleanup_task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    print(f"Serviço iniciado com limite de {MAX_SESSIONS} sessões e timeout de {SESSION_TIMEOUT_MINUTES} minutos")


async def periodic_cleanup():
    """Periodically clean up expired sessions."""
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            removed = await session_manager.cleanup_expired_sessions()
            if removed > 0:
                print(f"[Cleanup] Removidas {removed} sessões expiradas")
                # Force garbage collection after cleanup
                gc.collect()
        except Exception as e:
            print(f"[Cleanup] Erro durante limpeza periódica: {e}")


@app.post("/api/message", response_model=MessageResponse)
async def process_message(request: MessageRequest = Body(...)):
    """
    Processa uma mensagem de um usuário com gerenciamento automático de sessão.
    """
    try:
        # Get or create session
        session_id, bot = await session_manager.get_or_create_session(
            request.session_id,
            request.persona_id,
            executor
        )

        # Log timing metadata if present
        if request.timing_metadata:
            print(f"[Session {session_id}] Received timing metadata:")
            print(f"  - Timestamp simulado: {request.timing_metadata.get('simulated_timestamp', 'N/A')}")
            print(f"  - Tempo de reflexão: {request.timing_metadata.get('thinking_time', 0):.2f} segundos")
            print(f"  - Tempo de digitação: {request.timing_metadata.get('typing_time', 0):.2f} segundos")
            print(f"  - Tempo de pausa: {request.timing_metadata.get('break_time', 0):.2f} segundos")

        # Process message asynchronously
        response = await bot.aprocess_message(request.message)
        return MessageResponse(response=response, session_id=session_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar mensagem: {str(e)}")


@app.get("/api/sessions")
async def list_sessions():
    """Lista todas as sessões ativas com informações de timeout."""
    return await session_manager.get_session_info()


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Remove uma sessão específica do sistema."""
    log_path = await session_manager.remove_session(session_id)

    if log_path is None:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")

    return {
        "status": "success",
        "message": f"Sessão {session_id} removida",
        "log_path": log_path
    }


@app.get("/api/sessions/{session_id}/logs")
async def get_session_logs(session_id: str):
    """Obtém o arquivo ZIP de logs de uma sessão específica."""
    async with session_manager.lock:
        if session_id not in session_manager.bot_instances:
            raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")

        bot = session_manager.bot_instances[session_id]

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
    """Endpoint para verificação de saúde do serviço com estatísticas de memória."""
    session_info = await session_manager.get_session_info()

    response = {
        "status": "ok",
        "service": "BancoBot API",
        "version": "2.0.0",
        "sessions": {
            "active": session_info["count"],
            "max": session_info["max_sessions"]
        },
        "uptime_seconds": (datetime.now() - startup_time).total_seconds() if 'startup_time' in globals() else 0
    }

    # Try to get memory usage info if psutil is available
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        response["memory"] = {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024
        }
    except ImportError:
        response["memory"] = {
            "status": "psutil not installed",
            "install_command": "pip install psutil"
        }

    return response


@app.post("/api/cleanup")
async def force_cleanup(background_tasks: BackgroundTasks):
    """Força uma limpeza manual de sessões expiradas."""
    background_tasks.add_task(session_manager.cleanup_expired_sessions)
    return {"status": "cleanup_scheduled"}


@app.on_event("shutdown")
async def shutdown_event():
    """Limpa todos os recursos ao encerrar o serviço."""
    global cleanup_task

    print("Encerrando serviço...")

    # Cancel cleanup task
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

    # Generate logs for all active sessions
    print("Gerando logs para todas as sessões ativas...")
    session_ids = list(session_manager.bot_instances.keys())

    for session_id in session_ids:
        try:
            await session_manager.remove_session(session_id)
        except Exception as e:
            print(f"[Session {session_id}] Erro ao gerar logs: {e}")

    # Shutdown executor
    executor.shutdown(wait=True)
    print("Executor encerrado.")

    # Force final garbage collection
    gc.collect()
    print("Shutdown completo.")


# Track startup time
startup_time = datetime.now()


def start_server(host="0.0.0.0", port=8080):
    """Inicia o servidor FastAPI com configurações otimizadas."""
    # Configure garbage collection for better memory management
    gc.set_threshold(700, 10, 10)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()