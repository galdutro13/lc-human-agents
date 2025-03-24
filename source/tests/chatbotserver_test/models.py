from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class MessageRequest(BaseModel):
    """Requisição de mensagem para os chatbots."""
    message: str
    thread_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    """Resposta de mensagem dos chatbots."""
    message: str
    thread_id: str
    metadata: Optional[Dict[str, Any]] = None
    terminated: bool = False


class ChatConfig(BaseModel):
    """Configuração para inicialização dos chatbots."""
    think_exp: bool = False
    system_message: Optional[str] = None
    use_sqlitesaver: bool = False


class ChatStatus(BaseModel):
    """Status do chatbot."""
    thread_id: str
    is_active: bool
    last_activity: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None