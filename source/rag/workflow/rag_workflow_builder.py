from typing import Dict, Any, Optional, Callable
from langgraph.graph import StateGraph, START, END

from source.chat_graph.workflow_builder import Builder
from source.chat_graph.chat_function import ChatFunction

from source.rag.state.rag_state import RAGState
from source.rag.functions.rag_functions import RouterFunction, GraderFunction, RAGResponseFunction, FallbackFunction


class RAGWorkflowBuilder(Builder):
    """
    Builder for RAG workflows.
    Implements the Builder interface for compatibility with the existing system.
    """

    def __init__(self):
        """
        Initializes the RAGWorkflowBuilder.
        """
        self._workflow = StateGraph(RAGState)

    def build_workflow(self) -> Any:
        """
        Compiles and returns the workflow.

        Returns:
            Compiled workflow
        """
        return self._workflow.compile()

    def add_node(self, name: str, function: ChatFunction) -> 'RAGWorkflowBuilder':
        """
        Adds a node to the workflow.

        Args:
            name: Name of the node
            function: Function to execute at the node

        Returns:
            Self for method chaining
        """
        self._workflow.add_node(name, function)
        return self

    def add_edge(self, to_node: str, from_node: str = START) -> 'RAGWorkflowBuilder':
        """
        Adds an edge between nodes.

        Args:
            to_node: Destination node
            from_node: Source node (defaults to START)

        Returns:
            Self for method chaining
        """
        self._workflow.add_edge(from_node, to_node)
        return self

    def add_conditional_edge(self, from_node: str, condition_function: Callable,
                             routes: Dict[str, str]) -> 'RAGWorkflowBuilder':
        """
        Adds conditional edges from a node.

        Args:
            from_node: Source node
            condition_function: Function to determine the route
            routes: Mapping of condition results to destination nodes

        Returns:
            Self for method chaining
        """
        self._workflow.add_conditional_edges(from_node, condition_function, routes)
        return self

    def build_rag_workflow(self, router: RouterFunction, grader: GraderFunction,
                           responder: RAGResponseFunction, fallback: FallbackFunction) -> Any:
        """
        Builds a complete RAG workflow with all required components.

        Args:
            router: Router function for selecting datasources
            grader: Grader function for assessing document relevance
            responder: Function for generating responses from relevant documents
            fallback: Function for handling cases with no relevant documents

        Returns:
            Compiled RAG workflow
        """

        # Define conditional routing function
        def decide_next_step(state: RAGState) -> str:
            """
            Decides the next step based on document relevance.

            Args:
                state: Current workflow state

            Returns:
                Route to take
            """
            print("---DECIDE NEXT STEP---")
            if state.documents_relevant:
                print("Documents are relevant. Generating response.")
                return "relevant"
            else:
                print("Documents are not relevant. Responding with fallback.")
                return "irrelevant"

        # Add nodes
        self.add_node("route", router)
        self.add_node("retrieve", self._create_retriever_function())
        self.add_node("grade", grader)
        self.add_node("respond_with_relevant", responder)
        self.add_node("respond_with_fallback", fallback)

        # Set entry point
        self._workflow.set_entry_point("route")

        # Add regular edges
        self.add_edge("retrieve", "route")
        self.add_edge("grade", "retrieve")

        # Add conditional edges
        self.add_conditional_edge("grade", decide_next_step, {
            "relevant": "respond_with_relevant",
            "irrelevant": "respond_with_fallback"
        })

        # Add end edges
        self._workflow.add_edge("respond_with_relevant", END)
        self._workflow.add_edge("respond_with_fallback", END)

        # Compile and return the workflow
        return self.build_workflow()

    def _create_retriever_function(self) -> Callable:
        """
        Creates a function to retrieve documents from the selected datasource.

        Returns:
            Function to retrieve documents
        """

        def retrieve_from_datasource(state: RAGState) -> Dict[str, Any]:
            """
            Retrieves documents from the selected datasource.

            Args:
                state: Current workflow state

            Returns:
                Updated state with retrieved documents
            """
            print("---RETRIEVE FROM DATASOURCE---")

            # In the actual implementation, this function would use a retriever
            # to get documents from the selected datasource. For now, it's a placeholder.
            # The actual retrieval happens in the RAGResponseFunction.

            # Return empty context for now
            return {"context": []}

        return retrieve_from_datasource