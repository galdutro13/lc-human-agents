# source/rag/functions/cleanup_docs.py (MODIFIED)
from typing import Dict, Any, Optional

from source.chat_graph.chat_function import ChatFunction
from source.rag.state.rag_state import RAGState
from source.rag.logging.rag_logger import RAGLogger, rag_function_logger

class CleanupAggregatedDocsFunction(ChatFunction):
    """
    Cleans up the aggregated documents after completion of the workflow.
    This ensures that subsequent queries start with a clean slate.
    """

    def __init__(self, logger: Optional[RAGLogger] = None):
        self._logger = logger

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Cleans up the aggregated documents from the state.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary with empty aggregated_docs
        """
        with rag_function_logger(self._logger, "CleanupAggregatedDocsFunction", state):
            print("---CLEANUP AGGREGATED DOCS---")

            # Get the current count for logging purposes
            current_count = len(state.get('aggregated_docs', []))
            print(f"Cleaning up {current_count} aggregated documents")

            # Log cleanup
            if self._logger:
                self._logger.log("INFO", "Cleaning up aggregated documents", {
                    "documents_cleaned": current_count
                })

            # Return only the cleaned field
            return {"aggregated_docs": []}

    @property
    def prompt(self) -> Any:
        return None

    @property
    def model(self) -> Any:
        return None