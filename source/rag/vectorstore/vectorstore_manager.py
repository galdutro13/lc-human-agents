import os
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Union, Optional

from langchain.docstore.document import Document
from langchain_openai import OpenAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from source.rag.config.models import RAGConfig, EmbeddingConfig


class EmbeddingModelFactory:
    """
    Factory for creating embedding models.
    Provides a centralized way to create embedding models based on configuration.
    """

    @staticmethod
    def create_embedding_model(config: EmbeddingConfig) -> Union[OpenAIEmbeddings, HuggingFaceEmbeddings]:
        """
        Creates an embedding model based on the configuration.

        Args:
            config: Embedding model configuration

        Returns:
            An instance of an embedding model

        Raises:
            ValueError: If the provider is not supported
        """
        if config.provider.lower() == "openai":
            kwargs = {"model": config.model}
            if config.batch_size:
                kwargs["batch_size"] = config.batch_size
            return OpenAIEmbeddings(**kwargs)

        elif config.provider.lower() == "huggingface":
            return HuggingFaceEmbeddings(model_name=config.model,
                                         model_kwargs=config.model_kwargs)

        else:
            raise ValueError(f"Unsupported embedding provider: {config.provider}")


class VectorStoreFactory(ABC):
    """
    Abstract factory for creating vector stores.
    Defines a common interface for all vector store factories.
    """

    @abstractmethod
    def create_vectorstores(self, documents: Dict[str, List[Document]],
                            config: RAGConfig) -> Dict[str, Any]:
        """
        Creates vector stores for the provided documents.

        Args:
            documents: Dictionary mapping datasource names to lists of documents
            config: RAG system configuration

        Returns:
            Dictionary mapping datasource names to vector stores
        """
        pass


class ChromaVectorStoreFactory(VectorStoreFactory):
    """
    Factory for creating Chroma vector stores.
    Handles creation, persistence, and loading of Chroma vector stores.
    """

    def _get_client_settings(self):
        """
        Creates client settings for Chroma to disable the default embedding function.

        Returns:
            Client settings for Chroma
        """
        try:
            from chromadb.config import Settings
            # Disable default embedding function to avoid onnxruntime issues
            return Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                is_persistent=True
            )
        except ImportError:
            print("Warning: Could not import chromadb.config.Settings. Using default settings.")
            return None

    def create_vectorstores(self, documents: Dict[str, List[Document]],
                            config: RAGConfig) -> Dict[str, Chroma]:
        """
        Creates Chroma vector stores for the provided documents.

        Args:
            documents: Dictionary mapping datasource names to lists of documents
            config: RAG system configuration

        Returns:
            Dictionary mapping datasource names to Chroma vector stores
        """
        # Create the embedding model
        embeddings = EmbeddingModelFactory.create_embedding_model(config.embedding_config)

        # Create vector stores for each datasource
        vectorstores = {}

        for datasource_name, docs in documents.items():
            # Create a specific directory for this datasource
            datasource_directory = os.path.join(
                config.vectorstore_config.persist_directory,
                datasource_name.replace(" ", "_")
            )

            # Check if the vector store already exists
            vectorstore_exists = os.path.exists(datasource_directory)

            if vectorstore_exists and config.vectorstore_config.provider.lower() == "chroma":
                try:
                    # Try to load the existing vector store
                    print(f"Loading existing vector store for datasource '{datasource_name}'...")
                    # Explicitly setting embedding_function prevents using default ONNX embeddings
                    vectorstore = Chroma(
                        persist_directory=datasource_directory,
                        embedding_function=embeddings,
                        client_settings=self._get_client_settings()  # Disable default embeddings
                    )

                    # Check if the vector store has data
                    collection = vectorstore._collection
                    if collection.count() > 0:
                        print(f"  - Vector store loaded with {collection.count()} embeddings")
                        vectorstores[datasource_name] = vectorstore
                        continue  # Skip to the next datasource without reindexing
                    else:
                        print(f"  - Existing vector store is empty, recreating...")
                except Exception as e:
                    print(f"  - Error loading existing vector store: {str(e)}")
                    print(f"  - Recreating vector store...")

            # If we reached here, we need to create a new vector store
            print(f"Creating vector store for datasource '{datasource_name}'...")

            # Check if there are documents to index
            if not docs:
                print(f"  - No documents to index for datasource '{datasource_name}', skipping...")
                continue

            # Create the vector store
            if config.vectorstore_config.provider.lower() == "chroma":
                vectorstore = Chroma.from_documents(
                    documents=docs,
                    embedding=embeddings,
                    persist_directory=datasource_directory
                )
                vectorstore.persist()
                print(f"  - Vector store created and persisted in {datasource_directory}")
            else:
                raise ValueError(f"Unsupported vector store provider: {config.vectorstore_config.provider}")

            # Store the vector store in the dictionary
            vectorstores[datasource_name] = vectorstore

        return vectorstores