from abc import ABC, abstractmethod
from typing import Optional

from source.persona.persona import Persona
from source.prompt_manager.constantes import template_padrao, template_agressivo
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

class SystemPromptStrategy(ABC):
    """
    Interface para diferentes estratégias de geração de templates de prompt.
    """

    @abstractmethod
    def generate_prompt(self) -> ChatPromptTemplate:
        """
        Gera um prompt com base na estratégia definida.

        :return: Um objeto ChatPromptTemplate configurado.
        """
        pass


class DefaultSystemPromptStrategy(SystemPromptStrategy):
    """
    Gera um template de um agente usuário de comportamento padrão.
    O usuário está com a missão de buscar ajuda pois esqueceu sua senha do cartão.
    """

    def generate_prompt(self) -> ChatPromptTemplate:
        prompt: ChatPromptTemplate = ChatPromptTemplate.from_messages([
            ("system", template_padrao),
            MessagesPlaceholder(variable_name="messages"),
        ])
        return prompt


class AggressiveSystemPromptStrategy(SystemPromptStrategy):
    """
    Gera um template de um agente usuário de comportamento agressivo.
    O usuário está com a missão de buscar ajuda pois esqueceu sua senha do cartão.
    """

    def generate_prompt(self) -> ChatPromptTemplate:
        prompt: ChatPromptTemplate = ChatPromptTemplate.from_messages([
            ("system", template_agressivo),
            MessagesPlaceholder(variable_name="messages"),
        ])
        return prompt


class CustomSystemPromptStrategy(SystemPromptStrategy):
    """
    Gera um template de um agente usuário com base em um template de prompt personalizado.
    """

    def __init__(self, prompt_template: str):
        if not prompt_template:
            raise ValueError("O template personalizado não pode ser vazio.")
        self.prompt_template = prompt_template

    def generate_prompt(self) -> ChatPromptTemplate:
        prompt: ChatPromptTemplate = ChatPromptTemplate.from_messages([
            ("system", self.prompt_template),
            MessagesPlaceholder(variable_name="messages"),
        ])
        return prompt


class GenerativeSystemPromptStrategy(SystemPromptStrategy):
    """
    Gera um template de um agente usuário com base em um modelo de linguagem generativo.
    """
    def __init__(self, persona: Persona):
        few_shot = self._gen_few_shot(persona)
        llm = self._instantiate_llm(few_shot)
        self.prompt_template = self._gen_prompt(llm)

    def _gen_few_shot(self, persona: Persona):
        pass
    def _instantiate_llm(self, few_shot_template):
        pass
    def _gen_prompt(self, llm):
        pass
    def generate_prompt(self) -> ChatPromptTemplate:
        pass



class SystemPromptGenerator:
    """
    Classe responsável por gerar o prompt do sistema usando a estratégia fornecida.
    """

    def __init__(self, strategy: SystemPromptStrategy):
        """
        Inicializa o SystemPromptGenerator com a estratégia especificada.

        :param strategy: Instância de PromptGenerator para gerar o prompt.
        """
        if not isinstance(strategy, SystemPromptStrategy):
            raise TypeError("A estratégia deve ser uma instância de PromptGenerator.")
        self._strategy = strategy

    def generate_prompt(self) -> ChatPromptTemplate:
        """
        Gera o prompt usando a estratégia definida.

        :return: Um objeto ChatPromptTemplate configurado.
        """
        return self._strategy.generate_prompt()


