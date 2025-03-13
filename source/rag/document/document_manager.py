import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type

from langchain.docstore.document import Document
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader

from source.rag.config.models import RAGConfig, Datasource


class DocumentLoader(ABC):
    """
    Abstract base class for document loading strategies.
    Defines a common interface for all document loaders.
    """

    @abstractmethod
    def load_documents(self, config: RAGConfig, base_path: str) -> Dict[str, List[Document]]:
        """
        Loads documents according to the configuration.

        Args:
            config: RAG system configuration
            base_path: Base path for document loading

        Returns:
            Dictionary mapping datasource names to lists of loaded documents
        """
        pass


class FileSystemDocumentLoader(DocumentLoader):
    """
    Loads documents from the file system based on configuration.
    Supports various file types like PDF and DOCX.
    """

    def load_documents(self, config: RAGConfig, base_path: str) -> Dict[str, List[Document]]:
        """
        Loads documents from the file system according to the configuration.

        Args:
            config: RAG system configuration
            base_path: Base path for document loading

        Returns:
            Dictionary mapping datasource names to lists of loaded documents
        """
        documents_by_datasource = {}

        # Supported extensions and their corresponding loaders
        loaders = {
            ".docx": Docx2txtLoader,
            ".pdf": PyPDFLoader
        }

        # For each datasource defined in the configuration
        for datasource in config.datasources:
            datasource_folder_name = datasource.display_name
            print(f"Processing datasource '{datasource_folder_name}'...")
            documents_by_datasource[datasource.name] = []

            # For each folder associated with this datasource
            for folder_path in datasource.folders:
                folder_full_path = os.path.join(base_path, datasource_folder_name, folder_path)
                print(f"  Processing folder '{folder_path}' at {folder_full_path}")

                if not os.path.exists(folder_full_path):
                    print(f"  Warning: Folder '{folder_path}' not found, skipping...")
                    continue

                # Recursively walk through all folders and subfolders
                for root, _, files in os.walk(folder_full_path):
                    for file in files:
                        # Get the file extension
                        _, extension = os.path.splitext(file)
                        extension = extension.lower()

                        # Check if the extension is supported
                        if extension in loaders:
                            full_path = os.path.join(root, file)
                            try:
                                # Use the appropriate loader for the file type
                                loader = loaders[extension](full_path)

                                # Load and add metadata about the source
                                docs = loader.load()

                                # Add additional metadata for each document
                                for doc in docs:
                                    # Preserve original metadata and add new ones
                                    doc.metadata.update({
                                        "file_path": full_path,
                                        "file_name": file,
                                        "file_type": extension[1:],  # Remove the dot from the extension
                                        "datasource": datasource.name,
                                        "datasource_display_name": datasource.display_name,
                                        "subfolder": os.path.relpath(root, base_path)
                                    })

                                # Add the documents to the list of the corresponding datasource
                                documents_by_datasource[datasource.name].extend(docs)
                                print(f"    Loaded: {full_path}")
                            except Exception as e:
                                print(f"    Error loading {full_path}: {str(e)}")

        # Summary information
        total_docs = sum(len(docs) for docs in documents_by_datasource.values())
        print(f"\nLoading summary:")
        print(f"Total datasources: {len(documents_by_datasource)}")
        print(f"Total documents: {total_docs}")

        for name, docs in documents_by_datasource.items():
            datasource = next((ds for ds in config.datasources if ds.name == name), None)
            display_name = datasource.display_name if datasource else name
            print(f"  - Datasource '{display_name}': {len(docs)} documents")

        return documents_by_datasource


class DocumentProcessingFactory:
    """
    Factory for creating document processing components.
    Centralizes creation of text splitters and other document processing tools.
    """

    @staticmethod
    def create_text_splitter(config: RAGConfig):
        """
        Creates a text splitter based on the configuration.

        Args:
            config: RAG system configuration

        Returns:
            A configured text splitter
        """
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        kwargs = {
            "chunk_size": config.text_splitter.chunk_size,
            "chunk_overlap": config.text_splitter.chunk_overlap
        }

        if config.text_splitter.separators:
            kwargs["separators"] = config.text_splitter.separators

        return RecursiveCharacterTextSplitter(**kwargs)

