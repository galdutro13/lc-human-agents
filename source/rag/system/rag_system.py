# source/rag/system/rag_system.py (MODIFIED)
import os
import shutil
from typing import Dict, Any, Optional, List

from langgraph.checkpoint.base import BaseCheckpointSaver

from source.constantes.models import ModelName
from source.chat_graph.llms import get_llm

from source.rag.config import ConfigurationManager, YAMLConfigurationStrategy, RAGConfig
from source.rag.document import FileSystemDocumentLoader, StandardDocumentProcessor
from source.rag.vectorstore import ChromaVectorStoreFactory
from source.rag.functions import (
    RouterFunction, GraderFunction, RAGResponseFunction, FallbackFunction,
    RewriteQueryFunction, AggregateDocsFunction, CleanupAggregatedDocsFunction
)
from source.rag.workflow import RAGWorkflowBuilder

# Import the logger
from source.rag.logging.rag_logger import RAGLogger


class RAGSystem:
    """
    Main facade for the RAG system.
    Provides a simplified interface to the entire RAG system.
    """

    def __init__(self,
                 base_path: str,
                 thread_id: dict[str, dict[str, str]],
                 memory: BaseCheckpointSaver[str] = None,
                 model_name: ModelName = ModelName.GPT4,
                 logger: Optional[RAGLogger] = None,
                 persona_id: Optional[str] = None):
        """
        Initializes the RAG system.

        Args:
            base_path: Base path for configuration and documents
            thread_id: Thread configuration dict
            memory: Memory/checkpoint saver
            model_name: Name of the language model to use
            logger: Optional RAGLogger instance
            persona_id: Optional persona ID for logging
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

        # Logging setup
        self._logger = logger
        if self._logger is None and persona_id:
            # Create a default logger if persona_id is provided
            thread_id_str = thread_id.get("configurable", {}).get("thread_id", "unknown")
            self._logger = RAGLogger(thread_id_str, persona_id)

        # Message counter for logging
        self._message_count = 0

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

        # Create RAG components with logger support
        router = RouterFunction(self._config, list(self._vectorstores.keys()), model, logger=self._logger)
        grader = GraderFunction(self._config, model, logger=self._logger)
        responder = RAGResponseFunction(self._config, self._vectorstores, model, logger=self._logger)
        fallback = FallbackFunction(self._config, model, logger=self._logger)

        # Componentes para o fluxo de reescrita e loop
        rewriter = RewriteQueryFunction(self._config, model, logger=self._logger)
        aggregator = AggregateDocsFunction(logger=self._logger)

        # Nova função de limpeza
        cleanup = CleanupAggregatedDocsFunction(logger=self._logger)

        # Build the workflow
        builder = RAGWorkflowBuilder()
        return builder.build_rag_workflow(
            router=router,
            grader=grader,
            responder=responder,
            fallback=fallback,
            rewriter=rewriter,
            aggregator=aggregator,
            cleanup=cleanup,
            memory=self._memory,
            logger=self._logger  # Pass logger to workflow builder
        )

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

        # Start logging for new message if logger is available
        if self._logger:
            self._logger.start_new_message(question)

        try:
            # Invoke the workflow
            result = self._workflow.invoke({"question": question}, self._thread_id)

            # Log final response
            if self._logger:
                response_type = "relevant" if result.get('documents_relevant') else "fallback"
                self._logger.log_final_response(
                    result.get('response', ''),
                    response_type
                )

            # Increment message count
            self._message_count += 1

            # Create a friendlier result format
            return {
                "question": question,
                "datasource": result.get('datasource'),
                "documents_relevant": result.get('documents_relevant'),
                "response": result.get('response'),
                "messages": result.get('messages', [])
            }

        except Exception as e:
            if self._logger:
                import traceback
                self._logger.log_error(
                    type(e).__name__,
                    str(e),
                    traceback.format_exc()
                )
            raise

    async def aquery(self, question: str) -> Dict[str, Any]:
        """
        Assíncrono: Queries the RAG system with a question.

        Args:
            question: Question to ask

        Returns:
            Result of the query including response and metadata

        Raises:
            ValueError: If the system is not initialized
        """
        if self._workflow is None:
            raise ValueError("RAG system not initialized. Call initialize() first.")

        # Start logging for new message if logger is available
        if self._logger:
            self._logger.start_new_message(question)

        try:
            # Invoke the workflow asynchronously
            result = await self._workflow.ainvoke({"question": question}, self._thread_id)

            # Log final response
            if self._logger:
                response_type = "relevant" if result.get('documents_relevant') else "fallback"
                self._logger.log_final_response(
                    result.get('response', ''),
                    response_type
                )

            # Increment message count
            self._message_count += 1

            # Create a friendlier result format
            return {
                "question": question,
                "datasource": result.get('datasource'),
                "documents_relevant": result.get('documents_relevant'),
                "response": result.get('response'),
                "messages": result.get('messages', [])
            }

        except Exception as e:
            if self._logger:
                import traceback
                self._logger.log_error(
                    type(e).__name__,
                    str(e),
                    traceback.format_exc()
                )
            raise

    def generate_logs_zip(self, output_path: Optional[str] = None) -> Optional[str]:
        """
        Generates a ZIP file with all logs from the current session.

        Args:
            output_path: Optional path for the ZIP file

        Returns:
            Path to the generated ZIP file, or None if no logger
        """
        if self._logger:
            return self._logger.generate_zip(output_path)
        return None

    def close(self):
        """
        Closes the RAG system and generates final logs.
        """
        if self._logger:
            self._logger.close()

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