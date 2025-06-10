# source/rag/workflow/rag_workflow_builder.py (MODIFIED)
from typing import Dict, Any, Optional, Callable
from langgraph.graph import StateGraph, START, END

from source.chat_graph.workflow_builder import Builder
from source.chat_graph.chat_function import ChatFunction

# Importa o RAGState refatorado
from source.rag.state.rag_state import RAGState
from source.rag.functions import (
    RouterFunction, GraderFunction, RetrieveFunction, RAGResponseFunction,
    FallbackFunction, RewriteQueryFunction, AggregateDocsFunction,
    prepare_next_query, prepare_for_grading, should_continue_loop,
    CleanupAggregatedDocsFunction
)
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from source.rag.logging.rag_logger import RAGLogger, log_state_transition


class RAGWorkflowBuilder(Builder):
    """
    Builder for RAG workflows.
    Implements the Builder interface for compatibility with the existing system.
    """

    def __init__(self):
        """
        Initializes the RAGWorkflowBuilder using the refactored RAGState.
        """
        # A inicialização do StateGraph usa o RAGState refatorado (TypedDict)
        self._workflow = StateGraph(RAGState)
        self._logger = None

    def build_workflow(self, memory: BaseCheckpointSaver[str] = None) -> Any:
        """
        Compiles and returns the workflow.
        """
        compile_args = {}
        if memory is not None:
            compile_args['checkpointer'] = memory

        # Adiciona interrupção antes dos nós que podem precisar de entrada humana ou revisão
        # compile_args['interrupt_before'] = ["route", "grade"] # Exemplo se quisesse interrupção

        return self._workflow.compile(**compile_args)

    def add_node(self, name: str, function: Callable) -> 'RAGWorkflowBuilder':  # Aceita Callable genérico
        """
        Adds a node to the workflow.
        """
        self._workflow.add_node(name, function)
        return self

    def add_edge(self, to_node: str, from_node: str = START) -> 'RAGWorkflowBuilder':
        """
        Adds an edge between nodes.
        """
        self._workflow.add_edge(from_node, to_node)
        return self

    def add_conditional_edge(self, from_node: str, condition_function: Callable[[RAGState], str],
                             routes: Dict[str, str]) -> 'RAGWorkflowBuilder':
        """
        Adds conditional edges from a node.
        """
        self._workflow.add_conditional_edges(from_node, condition_function, routes)
        return self

    def build_rag_workflow(self,
                           router: RouterFunction,
                           grader: GraderFunction,
                           responder: RAGResponseFunction,
                           fallback: FallbackFunction,
                           rewriter: RewriteQueryFunction,
                           aggregator: AggregateDocsFunction,
                           cleanup: CleanupAggregatedDocsFunction,
                           memory: Optional[BaseCheckpointSaver[str]] = None,
                           logger: Optional[RAGLogger] = None) -> Any:
        """
        Builds a complete RAG workflow with all required components,
        including the new query rewriting and looping functionality.
        """
        retriever = RetrieveFunction(responder.retrievers, logger=logger)
        self._logger = logger

        # Função condicional para determinar o próximo passo após a avaliação de documentos
        def decide_next_step(state: RAGState) -> str:
            """
            Decides the next step based on document relevance using dictionary access.

            Args:
                state: Current workflow state (RAGState TypedDict)

            Returns:
                Route to take ('relevant' or 'irrelevant')
            """
            print("---DECIDE NEXT STEP---")
            # Acesso via dicionário usando .get() para segurança
            documents_are_relevant = state.get('documents_relevant', False)
            relevant_docs = state.get('relevant_context', [])

            if documents_are_relevant and relevant_docs:
                print(f"Routing to 'relevant': {len(relevant_docs)} relevant documents found.")
                log_state_transition(logger, "grade", "respond_with_relevant",
                                   f"{len(relevant_docs)} relevant documents")
                return "relevant"
            else:
                print("Routing to 'irrelevant': No relevant documents found or relevance flag is False.")
                log_state_transition(logger, "grade", "respond_with_fallback",
                                   "No relevant documents")
                return "irrelevant"

        # Adiciona nós para o novo fluxo
        self.add_node("rewrite_query", rewriter)
        self.add_node("prepare_next_query", prepare_next_query)
        self.add_node("route", router)
        self.add_node("retrieve", retriever)
        self.add_node("aggregate_docs", aggregator)
        self.add_node("prepare_for_grading", prepare_for_grading)
        self.add_node("grade", grader)
        self.add_node("respond_with_relevant", responder)
        self.add_node("respond_with_fallback", fallback)
        self.add_node("cleanup_aggregated_docs", cleanup)  # Novo nó para limpeza

        # Define ponto de entrada
        self._workflow.set_entry_point("rewrite_query")

        # Fluxo inicial: reescrita de query
        self.add_edge(from_node="rewrite_query", to_node="prepare_next_query")

        # Loop: prepare_next_query -> route -> retrieve -> aggregate_docs -> conditional
        self.add_edge(from_node="prepare_next_query", to_node="route")
        self.add_edge(from_node="route", to_node="retrieve")
        self.add_edge(from_node="retrieve", to_node="aggregate_docs")

        # Aresta condicional após agregação: continuar o loop ou seguir para avaliação
        def should_continue_loop_with_logging(state: RAGState) -> str:
            result = should_continue_loop(state)
            if result == "continue_loop":
                log_state_transition(logger, "aggregate_docs", "prepare_next_query",
                                   "More queries to process")
            else:
                log_state_transition(logger, "aggregate_docs", "prepare_for_grading",
                                   "All queries processed")
            return result

        self.add_conditional_edge("aggregate_docs", should_continue_loop_with_logging, {
            "continue_loop": "prepare_next_query",  # Continua o loop
            "finish_loop": "prepare_for_grading"  # Sai do loop
        })

        # Após o loop, prepara os documentos agregados para avaliação
        self.add_edge(from_node="prepare_for_grading", to_node="grade")

        # Aresta condicional após avaliação: responder com documentos relevantes ou fallback
        self.add_conditional_edge("grade", decide_next_step, {
            "relevant": "respond_with_relevant",
            "irrelevant": "respond_with_fallback"
        })

        # Inclui a etapa de limpeza após as respostas
        self.add_edge(from_node="respond_with_relevant", to_node="cleanup_aggregated_docs")
        self.add_edge(from_node="respond_with_fallback", to_node="cleanup_aggregated_docs")

        # Final do fluxo após a limpeza
        self.add_edge(from_node="cleanup_aggregated_docs", to_node=END)

        return self.build_workflow(memory=memory)