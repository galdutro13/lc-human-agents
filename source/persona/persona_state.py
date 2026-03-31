# source/persona/persona_state.py
from typing import Optional

from langgraph.graph import MessagesState


class PersonaState(MessagesState):
    persona_id: str
    timing_metadata: dict[str, str | int | float]
    simulation_metadata: dict[str, str | int | float | bool]
    typing_speed_wpm: Optional[float] = None  # Velocidade de digitacao em palavras por minuto
