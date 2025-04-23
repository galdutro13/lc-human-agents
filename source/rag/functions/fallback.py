# source/rag/functions/fallback.py
from typing import Dict, Any

from langchain_core.messages import SystemMessage, AIMessage

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig
from source.rag.state.rag_state import RAGState

class FallbackFunction(ChatFunction):
    """
    Handles cases where no relevant documents are found.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, config: RAGConfig, model: Any):
        self._config = config
        self._model = model

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Generates a fallback response when documents are not relevant.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary updating the state with the fallback response and messages
        """
        print("---HANDLE IRRELEVANT DOCUMENTS (FALLBACK)---")

        # Acesso via dicionário com default
        question = state.get('question')
        messages = state.get('messages', [])  # Obtém histórico de mensagens

        if not question:
            print("No question in state for fallback.")
            generic_response = "I cannot provide an answer as the question is missing."
            ai_message = AIMessage(content=generic_response)
            return {"response": generic_response, "messages": [ai_message]}  # Atualização parcial

        try:
            # Usa o prompt de fallback da configuração em vez do prompt estático
            system_prompt = self._config.global_prompts.fallback_prompt

            # Prepara mensagens para o LLM: prompt do sistema + histórico
            messages_for_llm = [SystemMessage(content=system_prompt)] + messages

            response_ai = self._model.invoke(messages_for_llm)
            print("Fallback response generated.")

            # Retorna atualização parcial
            return {"response": response_ai.content, "messages": [response_ai]}

        except Exception as e:
            print(f"Error generating fallback response: {str(e)}")
            error_response = "I apologize, but I couldn't find relevant information to answer your question at this time."
            ai_message = AIMessage(content=error_response)
            # Retorna atualização parcial
            return {"response": error_response, "messages": [ai_message]}

    @property
    def prompt(self) -> Any:
        return None # Não usa um ChatPromptTemplate aqui

    @property
    def model(self) -> Any:
        return self._model