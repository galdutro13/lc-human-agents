from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

from source.chat_graph.chat_function import ChatFunction


class Builder(ABC):
    """
    Interface for the Builder pattern. Defines methods to build a workflow.
    """

    @abstractmethod
    def build_workflow(self) -> CompiledStateGraph:
        """
        Returns the compiled workflow.
        """
        pass

    @abstractmethod
    def add_node(self, name: str, function: ChatFunction) -> Builder:
        """
        Adds a node to the workflow.
        """
        pass

    @abstractmethod
    def add_edge(self, to_node: str, from_node: str = START) -> Builder:
        """
        Adds an edge between nodes.
        """
        pass


class ClassicWorkflowBuilder(Builder):
    """
    Builder to create custom workflows using StateGraph.
    """

    def __init__(self):
        """
        Initializes the WorkflowBuilder with an empty StateGraph.
        """
        self._workflow = StateGraph(state_schema=MessagesState)

    def build_workflow(self, memory: BaseCheckpointSaver[str] = None) -> CompiledStateGraph:
        """
        Returns the compiled workflow.
        """
        if memory is not None:
            return self._workflow.compile(checkpointer=memory)
        else:
            return self._workflow.compile()

    def add_node(self, name: str, function: ChatFunction) -> ClassicWorkflowBuilder:
        """
        Adds a node to the graph with the associated chat function.

        :param name: Name of the node.
        :param function: ChatFunction to be executed at the node.
        :return: The current instance to allow method chaining.
        """
        self._workflow.add_node(name, function)
        return self

    def add_edge(self, to_node: str, from_node: str = START) -> ClassicWorkflowBuilder:
        """
        Adds an edge between two nodes.

        :param to_node: Destination node name.
        :param from_node: Origin node name. Defaults to START.
        :return: The current instance to allow method chaining.
        """
        self._workflow.add_edge(from_node, to_node)
        return self

    def build_classic_workflow(self,
                               node_name: str,
                               function: ChatFunction,
                               memory: BaseCheckpointSaver[str]) -> CompiledStateGraph:
        """
        Generates a classic workflow.
        """
        self.add_edge(node_name)
        self.add_node(node_name, function)
        return self.build_workflow(memory)
