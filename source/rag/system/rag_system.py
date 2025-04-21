import os
import secrets
import shutil
from typing import Dict, Any, Optional, List

from langgraph.checkpoint.base import BaseCheckpointSaver

from source.chat_graph.models import ModelName
from source.chat_graph.llms import get_llm

from source.rag.config import ConfigurationManager, YAMLConfigurationStrategy, RAGConfig
from source.rag.document import FileSystemDocumentLoader, StandardDocumentProcessor
from source.rag.vectorstore import ChromaVectorStoreFactory
from source.rag.functions import RouterFunction, GraderFunction, RAGResponseFunction, FallbackFunction
from source.rag.workflow import RAGWorkflowBuilder

from IPython.display import display, Image

class RAGSystem:
    """
    Main facade for the RAG system.
    Provides a simplified interface to the entire RAG system.
    """

    def __init__(self,
                 base_path: str,
                 thread_id: dict[str, dict[str, str]],
                 memory: BaseCheckpointSaver[str] = None,
                 model_name: ModelName = ModelName.GPT4):
        """
        Initializes the RAG system.

        Args:
            base_path: Base path for configuration and documents
            model_name: Name of the language model to use
        """
        self._base_path = base_path
        self._model_name = model_name
        self._workflow = None
        self._config = None
        self._vectorstores = None
        self._documents = None
        self._processed_documents = None
        self._thread_id = thread_id
        self._memory = memory

    def initialize(self, reindex: bool = False) -> None:
        """
        Initializes the RAG system with all required components.

        Args:
            reindex: Whether to force reindexing of documents
        """
        # 1. Load configuration
        print("Loading configuration...")
        config_path = os.path.join(self._base_path, "config.yaml")
        config_manager = ConfigurationManager(YAMLConfigurationStrategy())
        config_manager.load(config_path)
        self._config = config_manager.config

        # 2. Handle reindexing
        if reindex and os.path.exists(self._config.vectorstore_config.persist_directory):
            print(
                f"Reindexing mode enabled. Deleting vector store directory: {self._config.vectorstore_config.persist_directory}")
            shutil.rmtree(self._config.vectorstore_config.persist_directory)

        # 3. Load documents
        print("Loading documents...")
        document_loader = FileSystemDocumentLoader()
        self._documents = document_loader.load_documents(self._config, self._base_path)

        # 4. Process documents
        print("Processing documents...")
        document_processor = StandardDocumentProcessor()
        self._processed_documents = document_processor.process_documents(self._documents, self._config)

        # 5. Create vector stores
        print("Creating/loading vector stores...")
        vectorstore_factory = ChromaVectorStoreFactory()
        self._vectorstores = vectorstore_factory.create_vectorstores(self._processed_documents, self._config)

        # 6. Create the workflow
        print("Building RAG workflow...")
        self._workflow = self._create_workflow()

        print("RAG system initialization complete!")

    def _create_workflow(self) -> Any:
        """
        Creates the RAG workflow with all required components.

        Returns:
            Compiled RAG workflow
        """
        # Get the language model
        model = get_llm(self._model_name)

        # Create RAG components
        router = RouterFunction(self._config, list(self._vectorstores.keys()), model)
        grader = GraderFunction(self._config, model)
        responder = RAGResponseFunction(self._config, self._vectorstores, model)
        fallback = FallbackFunction(self._config, model)

        # Build the workflow
        builder = RAGWorkflowBuilder()
        return builder.build_rag_workflow(router=router,
                                          grader=grader,
                                          responder=responder,
                                          fallback=fallback,
                                          memory=self._memory)

    def query(self, question: str) -> Dict[str, Any]:
        """
        Queries the RAG system with a question.

        Args:
            question: Question to ask

        Returns:
            Result of the query including response and metadata

        Raises:
            ValueError: If the system is not initialized
        """
        if self._workflow is None:
            raise ValueError("RAG system not initialized. Call initialize() first.")

        # Invoke the workflow
        result = self._workflow.invoke({"question": question}, self._thread_id)

        # Create a friendlier result format
        return {
            "question": question,
            "datasource": result.get('datasource'),
            "documents_relevant": result.get('documents_relevant'),
            "response": result.get('response'),
            "messages": result.get('messages', [])
        }

    @property
    def config(self) -> Optional[RAGConfig]:
        """
        Gets the system configuration.

        Returns:
            RAG system configuration or None if not initialized
        """
        return self._config

    @property
    def datasources(self) -> List[str]:
        """
        Gets the names of available datasources.

        Returns:
            List of datasource names or empty list if not initialized
        """
        if self._vectorstores is None:
            return []
        return list(self._vectorstores.keys())

    def visualize(self):
        try:
            print(self._workflow.get_graph().draw_mermaid())
        except ImportError:
            print(
                "You likely need to install dependencies for pygraphviz, see more here https://github.com/pygraphviz/pygraphviz/blob/main/INSTALL.txt"
            )