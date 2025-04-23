# source/rag/functions package
"""
RAG function implementations.
Provides implementations of ChatFunctions for use in RAG workflows.
"""

from source.rag.functions.rag_functions import (
    RouterFunction, GraderFunction, RetrieveFunction, RAGResponseFunction, FallbackFunction,
    # Novas funções para reescrita de query e loop
    RewriteQueryFunction, AggregateDocsFunction,
    # Funções auxiliares para controle de fluxo
    prepare_next_query, prepare_for_grading, should_continue_loop
)

__all__ = [
    'RouterFunction', 'GraderFunction', 'RetrieveFunction', 'RAGResponseFunction', 'FallbackFunction',
    'RewriteQueryFunction', 'AggregateDocsFunction',
    'prepare_next_query', 'prepare_for_grading', 'should_continue_loop'
]