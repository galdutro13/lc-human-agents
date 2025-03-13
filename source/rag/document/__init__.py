# source/rag/document package
"""
Document loading and processing for RAG systems.
Provides components for loading and preprocessing documents.
"""

from source.rag.document.document_manager import (
    DocumentLoader, FileSystemDocumentLoader, DocumentProcessingFactory
)
from source.rag.document.document_processor import (
    DocumentProcessor, StandardDocumentProcessor, TextSplitterFactory
)

__all__ = [
    'DocumentLoader', 'FileSystemDocumentLoader', 'DocumentProcessingFactory',
    'DocumentProcessor', 'StandardDocumentProcessor', 'TextSplitterFactory'
]