# source/rag/state/rag_state.py
from typing import List, Optional, TypedDict, Annotated
from langchain_core.messages import AnyMessage
# Importa MessagesState que já inclui o campo 'messages' e é baseado em TypedDict
from langgraph.graph import MessagesState, add_messages

# RAGState agora herda de MessagesState
class RAGState(MessagesState):
    """
    State for the adaptive RAG workflow using TypedDict structure.
    Tracks the progress and data through the RAG pipeline.
    Inherits 'messages: Annotated[List[AnyMessage], add_messages]' from MessagesState.
    """
    # Define os outros campos do estado usando a sintaxe TypedDict
    question: str
    datasource: Optional[str]
    context: List[str]           # Todos os documentos recuperados
    relevant_context: List[str]  # Apenas documentos relevantes
    documents_relevant: bool     # True se pelo menos um documento for relevante
    response: Optional[str]

