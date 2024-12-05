from abc import ABC, abstractmethod
from typing import Any

from langgraph.graph import MessagesState


class ChatFunction(ABC):
    """
    Abstract base class representing a chat function.
    """

    @abstractmethod
    def __call__(self, state: MessagesState) -> dict:
        """
        Execute the chat function with the given state.
        """
        pass

    @property
    @abstractmethod
    def prompt(self) -> Any:
        """
        Get the prompt used by the chat function.
        """
        pass

    @property
    @abstractmethod
    def model(self) -> Any:
        """
        Get the model used by the chat function.
        """
        pass


class ClassicChatFunction(ChatFunction):
    """
    Classic implementation of a ChatFunction using a prompt and a model.
    """

    def __init__(self, prompt: Any, model: Any):
        self._prompt = prompt
        self._model = model

    def __call__(self, state: MessagesState) -> dict:
        chain = self._prompt | self._model
        response = chain.invoke(state)
        return {"messages": response}

    @property
    def prompt(self) -> Any:
        return self._prompt

    @property
    def model(self) -> Any:
        return self._model
