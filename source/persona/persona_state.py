# source/persona/persona_state.py
from typing import Optional
from langgraph.graph import MessagesState

class PersonaState(MessagesState):
    persona_id: str
    timing_metadata: dict[str, str | int | float]
    typing_speed_wpm: Optional[float] = None  # Velocidade de digitação em palavras por minuto