# source/rag/functions/retrieve.py (MODIFIED)
from typing import Dict, Any, Optional

from source.chat_graph.chat_function import ChatFunction
from source.rag.state.rag_state import RAGState
from source.rag.logging.rag_logger import RAGLogger, rag_function_logger


class RetrieveFunction(ChatFunction):
    """
    Retrieves documents from the selected datasource.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, retrievers: Dict[str, Any], logger: Optional[RAGLogger] = None):
        self._retrievers = retrievers
        self._logger = logger

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Retrieves documents from the selected datasource.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary to update the state with retrieved documents
        """
        with rag_function_logger(self._logger, "RetrieveFunction", state):
            print("---RETRIEVE FROM DATASOURCE---")

            # Acesso via dicionário
            datasource = state.get('datasource')
            question = state.get('question')

            # Verifica se a datasource foi definida
            if not datasource or datasource not in self._retrievers:
                print(f"Datasource '{datasource}' not found or not selected.")
                if self._logger:
                    self._logger.log("WARNING",
                                     f"Datasource '{datasource}' not found or not selected",
                                     {"available_datasources": list(self._retrievers.keys())})

                # Fallback para a primeira datasource disponível, se houver
                if self._retrievers:
                    datasource = next(iter(self._retrievers.keys()))
                    print(f"Falling back to the first available datasource: '{datasource}'")
                else:
                    print("No datasources available to retrieve from.")
                    return {"context": []}

            # Verifica se a questão foi definida
            if not question:
                print("No question found in state.")
                if self._logger:
                    self._logger.log("WARNING", "No question found in state for retrieval")
                return {"context": []}

            try:
                retriever = self._retrievers[datasource]
                docs = retriever.invoke(question)
                print(
                    f"Retrieved {len(docs)} documents from datasource '{datasource}' for question: '{question[:50]}...'")

                context = [doc.page_content for doc in docs]

                # Log retrieval details
                if self._logger:
                    docs_preview = [doc[:200] + "..." if len(doc) > 200 else doc for doc in context[:3]]
                    self._logger.log_retrieval(datasource, question, len(docs), docs_preview)

                return {"context": context}

            except Exception as e:
                print(f"Error retrieving documents from '{datasource}': {str(e)}")
                if self._logger:
                    import traceback
                    self._logger.log_error("RetrievalError", str(e), traceback.format_exc())
                return {"context": []}

    @property
    def prompt(self) -> Any:
        return None

    @property
    def model(self) -> Any:
        return None