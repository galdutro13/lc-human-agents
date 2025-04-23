# source/rag/functions/aggregate_docs.py
from typing import Dict, Any

from source.chat_graph.chat_function import ChatFunction
from source.rag.state.rag_state import RAGState

class AggregateDocsFunction(ChatFunction):
    """
    Aggregates retrieved documents from multiple queries.
    """

    def __init__(self):
        pass

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Aggregates retrieved documents and updates the loop state.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary updating the state with aggregated documents and loop control
        """
        print("---AGGREGATE DOCUMENTS---")

        # Access via dictionary with defaults
        current_index = state.get('current_query_index', 0)
        rewritten_queries = state.get('rewritten_queries', [])
        context = state.get('context', [])
        aggregated_docs = state.get('aggregated_docs', [])

        # Add current context to aggregated documents (avoiding duplicates)
        for doc in context:
            if doc not in aggregated_docs:
                aggregated_docs.append(doc)

        # Update the index for the next iteration
        next_index = current_index + 1
        has_more_queries = next_index < len(rewritten_queries)

        print(f"Aggregated {len(aggregated_docs)} unique documents so far.")
        print(f"Current query index: {current_index}, Next index: {next_index}")
        print(f"More queries available: {has_more_queries}")

        # Return updated state
        return {
            "current_query_index": next_index,
            "aggregated_docs": aggregated_docs,
            "has_more_queries": has_more_queries  # Flag for conditional edge
        }

    @property
    def prompt(self) -> Any:
        return None

    @property
    def model(self) -> Any:
        return None