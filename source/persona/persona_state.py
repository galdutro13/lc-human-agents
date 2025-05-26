from langgraph.graph import MessagesState

class PersonaState(MessagesState):
    persona_id: str
    timing_metadata: dict[str, str | int]