# source/rag/functions/aggregate_docs.py (MODIFIED)
from typing import Dict, Any, Optional

from source.chat_graph.chat_function import ChatFunction
from source.rag.state.rag_state import RAGState
from source.rag.logging.rag_logger import RAGLogger, rag_function_logger

class AggregateDocsFunction(ChatFunction):
    """
    Aggregates retrieved documents from multiple queries.
    """

    def __init__(self, logger: Optional[RAGLogger] = None):
        self._logger = logger

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Aggregates retrieved documents and updates the loop state.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary updating the state with aggregated documents and loop control
        """
        with rag_function_logger(self._logger, "AggregateDocsFunction", state):
            print("---AGGREGATE DOCUMENTS---")

            # Access via dictionary with defaults
            current_index = state.get('current_query_index', 0)
            rewritten_queries = state.get('rewritten_queries', [])
            context = state.get('context', [])
            aggregated_docs = state.get('aggregated_docs', [])

            # Add current context to aggregated documents (avoiding duplicates)
            new_docs_count = 0
            for doc in context:
                if doc not in aggregated_docs:
                    aggregated_docs.append(doc)
                    new_docs_count += 1

            # Update the index for the next iteration
            next_index = current_index + 1
            has_more_queries = next_index < len(rewritten_queries)

            print(f"Aggregated {len(aggregated_docs)} unique documents so far.")
            print(f"Current query index: {current_index}, Next index: {next_index}")
            print(f"More queries available: {has_more_queries}")

            # Log aggregation details
            if self._logger:
                self._logger.log("INFO", "Document aggregation", {
                    "new_documents": new_docs_count,
                    "total_aggregated": len(aggregated_docs),
                    "current_index": current_index,
                    "next_index": next_index,
                    "has_more_queries": has_more_queries
                })

            # Return updated state
            return {
                "current_query_index": next_index,
                "aggregated_docs": aggregated_docs,
                "has_more_queries": has_more_queries
            }

    @property
    def prompt(self) -> Any:
        return None

    @property
    def model(self) -> Any:
        return None