from langchain.prompts.chat import ChatPromptTemplate
from source.persona.persona import Persona
from source.prompt_manager.base import (
    SystemPromptGenerator,
    CustomSystemPromptStrategy
)

class CustomSystemPromptGenerator(CustomSystemPromptStrategy):
    def __init__(self, prompt_template: str, persona: Persona):

        pass

    def generate_prompt(self) -> ChatPromptTemplate:
        pass

    def persona_to_prompt(self, persona: Persona) -> str:
        pass
