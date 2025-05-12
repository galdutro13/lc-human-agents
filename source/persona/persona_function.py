from typing import Any

from source.chat_graph.chat_function import ChatFunction
from source.persona.persona_state import PersonaState

class PersonaChatFunction(ChatFunction):
    """
    Persona implementation of a ChatFunction using a prompt and a model.
    """

    def __init__(self, prompt: Any, model: Any):
        self._prompt = prompt
        self._model = model

    def __call__(self, state: PersonaState) -> dict:
        chain = self._prompt | self._model
        response = chain.invoke(state)
        return {"messages": response}

    @property
    def prompt(self) -> Any:
        return self._prompt

    @property
    def model(self) -> Any:
        return self._model