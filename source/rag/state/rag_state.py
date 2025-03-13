from typing import List, Optional
from pydantic import BaseModel


class RAGState(BaseModel):
    """
    State for the adaptive RAG workflow.
    Tracks the progress and data through the RAG pipeline.
    """
    question: str
    datasource: Optional[str] = None
    context: List[str] = []
    documents_relevant: bool = False
    response: Optional[str] = None