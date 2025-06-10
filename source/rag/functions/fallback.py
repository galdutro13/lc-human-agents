# source/rag/functions/fallback.py (MODIFIED)
from typing import Dict, Any, Optional

from langchain_core.messages import SystemMessage, AIMessage

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig
from source.rag.state.rag_state import RAGState
from source.rag.logging.rag_logger import RAGLogger, rag_function_logger

class FallbackFunction(ChatFunction):
    """
    Handles cases where no relevant documents are found.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, config: RAGConfig, model: Any, logger: Optional[RAGLogger] = None):
        self._config = config
        self._model = model
        self._logger = logger

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Generates a fallback response when documents are not relevant.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary updating the state with the fallback response and messages
        """
        with rag_function_logger(self._logger, "FallbackFunction", state):
            print("---HANDLE IRRELEVANT DOCUMENTS (FALLBACK)---")

            # Acesso via dicionário com default
            question = state.get('question')
            messages = state.get('messages', [])

            if not question:
                print("No question in state for fallback.")
                if self._logger:
                    self._logger.log("ERROR", "No question in state for fallback")
                generic_response = "I cannot provide an answer as the question is missing."
                ai_message = AIMessage(content=generic_response)
                return {"response": generic_response, "messages": [ai_message]}

            try:
                # Log fallback generation
                if self._logger:
                    self._logger.log("INFO", "Generating fallback response", {
                        "question": question,
                        "reason": "no_relevant_documents"
                    })

                # Usa o prompt de fallback da configuração
                system_prompt = self._config.global_prompts.fallback_prompt
                messages_for_llm = [SystemMessage(content=system_prompt)] + messages

                response_ai = self._model.invoke(messages_for_llm)
                print("Fallback response generated.")

                return {"response": response_ai.content, "messages": [response_ai]}

            except Exception as e:
                print(f"Error generating fallback response: {str(e)}")
                if self._logger:
                    import traceback
                    self._logger.log_error("FallbackGenerationError", str(e), traceback.format_exc())
                error_response = "I apologize, but I couldn't find relevant information to answer your question at this time."
                ai_message = AIMessage(content=error_response)
                return {"response": error_response, "messages": [ai_message]}

    @property
    def prompt(self) -> Any:
        return None

    @property
    def model(self) -> Any:
        return self._model