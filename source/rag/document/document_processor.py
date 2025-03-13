from typing import Dict, List, Union, Optional
from abc import ABC, abstractmethod

from langchain.docstore.document import Document
from langchain.text_splitter import TextSplitter, RecursiveCharacterTextSplitter

from source.rag.config.models import RAGConfig, TextSplitterConfig


class DocumentProcessor(ABC):
    """
    Abstract base class for document processing strategies.
    Defines a common interface for document processing operations.
    """

    @abstractmethod
    def process_documents(self, documents: Dict[str, List[Document]],
                          config: RAGConfig) -> Dict[str, List[Document]]:
        """
        Processes documents according to the configuration.

        Args:
            documents: Dictionary mapping datasource names to lists of documents
            config: RAG system configuration

        Returns:
            Dictionary mapping datasource names to lists of processed documents
        """
        pass


class TextSplitterFactory:
    """
    Factory for creating text splitters.
    Centralizes text splitter creation logic.
    """

    @staticmethod
    def create_text_splitter(config: TextSplitterConfig) -> TextSplitter:
        """
        Creates a text splitter based on the provided configuration.

        Args:
            config: Text splitter configuration

        Returns:
            Configured TextSplitter instance

        Raises:
            ValueError: If the text splitter type is not supported
        """
        if config.type.lower() == "recursive_character":
            kwargs = {
                "chunk_size": config.chunk_size,
                "chunk_overlap": config.chunk_overlap
            }

            if config.separators:
                kwargs["separators"] = config.separators

            return RecursiveCharacterTextSplitter(**kwargs)
        else:
            raise ValueError(f"Unsupported text splitter type: {config.type}")


class StandardDocumentProcessor(DocumentProcessor):
    """
    Standard implementation of document processing.
    Splits documents into chunks for vector storage.
    """

    def process_documents(self, documents: Dict[str, List[Document]],
                          config: RAGConfig) -> Dict[str, List[Document]]:
        """
        Processes documents by splitting them into chunks.

        Args:
            documents: Dictionary mapping datasource names to lists of documents
            config: RAG system configuration

        Returns:
            Dictionary mapping datasource names to lists of processed documents
        """
        # Create the text splitter
        text_splitter = TextSplitterFactory.create_text_splitter(config.text_splitter)

        processed_documents = {}

        # Process each datasource
        for datasource_name, docs in documents.items():
            print(f"Processing documents for datasource '{datasource_name}'...")

            if not docs:
                print(f"  No documents to process for datasource '{datasource_name}', skipping...")
                processed_documents[datasource_name] = []
                continue

            # Split documents into chunks
            chunks = text_splitter.split_documents(docs)
            print(f"  {len(docs)} documents split into {len(chunks)} chunks")

            # Store the processed documents
            processed_documents[datasource_name] = chunks

        return processed_documents