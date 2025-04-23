# source/rag/functions/flow_utils.py
from typing import Dict, Any

from source.rag.state.rag_state import RAGState

def prepare_next_query(state: RAGState) -> Dict[str, Any]:
    """
    Prepares the next rewritten query for processing.

    Args:
        state: Current workflow state (RAGState TypedDict)

    Returns:
        Updated state with the next query
    """
    print("---PREPARE NEXT QUERY---")
    rewritten_queries = state.get('rewritten_queries', [])
    current_index = state.get('current_query_index', 0)

    if current_index < len(rewritten_queries):
        next_query = rewritten_queries[current_index]
        print(f"Using rewritten query ({current_index + 1}/{len(rewritten_queries)}): {next_query}")
        return {"question": next_query}

    # Fallback to the original question if no more queries
    original_question = state.get('original_question', '')
    print(f"No more rewritten queries, falling back to original: {original_question}")
    return {"question": original_question}


def prepare_for_grading(state: RAGState) -> Dict[str, Any]:
    """
    Prepares the state for the final grading step.

    Args:
        state: Current workflow state (RAGState TypedDict)

    Returns:
        Updated state with aggregated documents as context
    """
    print("---PREPARE FOR GRADING---")
    original_question = state.get('original_question', '')
    aggregated_docs = state.get('aggregated_docs', [])

    print(f"Preparing for grading with original question: {original_question}")
    print(f"Using {len(aggregated_docs)} aggregated documents")

    return {
        "question": original_question,
        "context": aggregated_docs
    }


def should_continue_loop(state: RAGState) -> str:
    """
    Determines whether to continue the loop or move to grading.

    Args:
        state: Current workflow state (RAGState TypedDict)

    Returns:
        Route to take ('continue_loop' or 'finish_loop')
    """
    print("---CHECK LOOP CONDITION---")
    has_more_queries = state.get('has_more_queries', False)

    if has_more_queries:
        current_index = state.get('current_query_index', 0)
        rewritten_queries = state.get('rewritten_queries', [])
        if current_index < len(rewritten_queries):
            print(f"Continuing loop with query {current_index + 1}/{len(rewritten_queries)}")
            return "continue_loop"

    print("Loop complete, moving to grading")
    return "finish_loop"