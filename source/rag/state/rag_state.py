from typing import List, Optional, Annotated
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


class RAGState(BaseModel):
    """
    State for the adaptive RAG workflow.
    Tracks the progress and data through the RAG pipeline.
    """
    question: str
    datasource: Optional[str] = None
    context: List[str] = []  # All retrieved documents
    relevant_context: List[str] = []  # Only relevant documents
    documents_relevant: bool = False  # True if at least one document is relevant
    response: Optional[str] = None
    messages: Annotated[List[AnyMessage], add_messages] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True