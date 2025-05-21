from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class RetrieverConfig(BaseModel):
    """Configuration for document retrievers."""
    search_type: str = "similarity"
    top_k: int = 3
    fetch_k: Optional[int] = None
    lambda_mult: Optional[float] = None
    score_threshold: Optional[float] = None


class PromptTemplates(BaseModel):
    """Prompt templates specific to each datasource."""
    rag_prompt: str


class Datasource(BaseModel):
    """Configuration for a data source."""
    name: str
    display_name: str
    description: Optional[str] = None
    folders: List[str]
    prompt_templates: PromptTemplates
    retriever_config: RetrieverConfig


class ExternalTool(BaseModel):
    """Configuration for an external tool."""
    name: str
    display_name: str
    description: str
    trigger_keywords: List[str]
    api_endpoint: Optional[str] = None
    api_key_env: Optional[str] = None


class GlobalPrompts(BaseModel):
    """Global system prompts."""
    router_prompt: str
    grader_prompt: str
    fallback_prompt: str
    rewrite_query_prompt: str  # Novo campo para prompt de reescrita de query


class EmbeddingConfig(BaseModel):
    """Configuration for the embedding model."""
    model: str
    provider: str = "openai"
    batch_size: Optional[int] = None
    model_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Argumentos adicionais passados ao construtor do modelo (ex.: {'device':'cpu'})"
    )


class VectorstoreConfig(BaseModel):
    """Configuration for the vector database."""
    provider: str
    persist_directory: str


class LLMConfig(BaseModel):
    """Configuration for the language model."""
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class TextSplitterConfig(BaseModel):
    """Configuration for the text splitter."""
    type: str = "recursive_character"
    chunk_size: int = 1000
    chunk_overlap: int = 100
    separators: Optional[List[str]] = None


class RAGConfig(BaseModel):
    """Complete configuration for the RAG system."""
    version: str
    datasources: List[Datasource]
    global_prompts: GlobalPrompts
    embedding_config: EmbeddingConfig
    vectorstore_config: VectorstoreConfig
    llm_config: LLMConfig
    text_splitter: TextSplitterConfig
    external_tools: Optional[List[ExternalTool]] = None