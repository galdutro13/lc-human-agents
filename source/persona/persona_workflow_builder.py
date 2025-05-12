from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

from source.chat_graph import Builder
from source.persona import PersonaState, PersonaChatFunction

class PersonaWorkflowBuilder(Builder):
    """
    Builder to create custom workflows using StateGraph.
    """

    def __init__(self):
        """
        Initializes the WorkflowBuilder with an empty StateGraph.
        """
        self._workflow = StateGraph(state_schema=PersonaState)

    def build_workflow(self, memory: BaseCheckpointSaver[str] = None) -> CompiledStateGraph:
        """
        Returns the compiled workflow.
        """
        if memory is not None:
            return self._workflow.compile(checkpointer=memory)
        else:
            return self._workflow.compile()

    def add_node(self, name: str, function: PersonaChatFunction) -> 'PersonaWorkflowBuilder':
        """
        Adds a node to the graph with the associated chat function.

        :param name: Name of the node.
        :param function: PersonaChatFunction to be executed at the node.
        :return: The current instance to allow method chaining.
        """
        self._workflow.add_node(name, function)
        return self

    def add_edge(self, to_node: str, from_node: str = START) -> 'PersonaWorkflowBuilder':
        """
        Adds an edge between two nodes.

        :param to_node: Destination node name.
        :param from_node: Origin node name. Defaults to START.
        :return: The current instance to allow method chaining.
        """
        self._workflow.add_edge(from_node, to_node)
        return self

    def build_persona_workflow(self,
                               node_name: str,
                               function: PersonaChatFunction,
                               memory: BaseCheckpointSaver[str]) -> CompiledStateGraph:
        """
        Generates a classic workflow.
        """
        self.add_edge(node_name)
        self.add_node(node_name, function)
        return self.build_workflow(memory)