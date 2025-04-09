# source/rag/workflow/rag_workflow_builder.py
from typing import Dict, Any, Optional, Callable
from langgraph.graph import StateGraph, START, END

from source.chat_graph.workflow_builder import Builder
from source.chat_graph.chat_function import ChatFunction

# Importa o RAGState refatorado
from source.rag.state.rag_state import RAGState
from source.rag.functions.rag_functions import RouterFunction, GraderFunction, RetrieveFunction, RAGResponseFunction, \
    FallbackFunction
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver

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


    def add_node(self, name: str, function: Callable) -> 'RAGWorkflowBuilder': # Aceita Callable genérico
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
                           memory: Optional[BaseCheckpointSaver[str]] = None) -> Any:
        """
        Builds a complete RAG workflow with all required components.
        """
        retriever = RetrieveFunction(responder.retrievers)

        # Função condicional ajustada para acesso via dicionário
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
                return "relevant"
            else:
                print("Routing to 'irrelevant': No relevant documents found or relevance flag is False.")
                return "irrelevant"

        # Adiciona nós
        self.add_node("route", router)
        self.add_node("retrieve", retriever)
        self.add_node("grade", grader)
        self.add_node("respond_with_relevant", responder)
        self.add_node("respond_with_fallback", fallback)

        # Define ponto de entrada e arestas
        self._workflow.set_entry_point("route")
        self.add_edge(from_node="route", to_node="retrieve")
        self.add_edge(from_node="retrieve", to_node="grade")

        # Arestas condicionais baseadas na função ajustada
        self.add_conditional_edge("grade", decide_next_step, {
            "relevant": "respond_with_relevant",
            "irrelevant": "respond_with_fallback"
        })

        # Arestas para o final
        self.add_edge(from_node="respond_with_relevant", to_node=END)
        self.add_edge(from_node="respond_with_fallback", to_node=END)

        return self.build_workflow(memory=memory)