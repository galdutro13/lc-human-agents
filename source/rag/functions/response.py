# source/rag/functions/response.py (MODIFIED)
from typing import Dict, Any, Optional

from langchain_core.messages import SystemMessage, AIMessage
from langchain_community.vectorstores import Chroma

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig
from source.rag.state.rag_state import RAGState
from source.rag.logging.rag_logger import RAGLogger, rag_function_logger

class RAGResponseFunction(ChatFunction):
    """
    Generates responses from relevant documents.
    Implements the ChatFunction interface for compatibility with the existing system.
    """
    def __init__(self, config: RAGConfig, vectorstores: Dict[str, Chroma], model: Any,
                 logger: Optional[RAGLogger] = None):
        self._config = config
        self._vectorstores = vectorstores
        self._model = model
        self._retrievers = {}
        self._logger = logger
        self._initialize_retrievers()

    def _initialize_retrievers(self):
        for datasource_name, vectorstore in self._vectorstores.items():
            datasource = next((d for d in self._config.datasources if d.name == datasource_name), None)
            if not datasource: continue
            retriever_config = datasource.retriever_config
            retriever_kwargs = {"search_type": retriever_config.search_type, "search_kwargs": {}}
            if retriever_config.top_k: retriever_kwargs["search_kwargs"]["k"] = retriever_config.top_k
            if retriever_config.search_type == "mmr" and retriever_config.fetch_k:
                retriever_kwargs["search_kwargs"]["fetch_k"] = retriever_config.fetch_k
            if retriever_config.search_type == "mmr" and retriever_config.lambda_mult:
                retriever_kwargs["search_kwargs"]["lambda_mult"] = retriever_config.lambda_mult
            if retriever_config.score_threshold:
                retriever_kwargs["search_kwargs"]["score_threshold"] = retriever_config.score_threshold
            self._retrievers[datasource_name] = vectorstore.as_retriever(**retriever_kwargs)

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Generates a response based on relevant documents.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary updating the state with the generated response and messages
        """
        with rag_function_logger(self._logger, "RAGResponseFunction", state):
            print("---GENERATE RESPONSE FROM RELEVANT DOCS---")

            # Acesso via dicionário com defaults
            question = state.get('question')
            datasource = state.get('datasource')
            relevant_context = state.get('relevant_context', [])
            messages = state.get('messages', [])

            # Validações
            if not question:
                print("No question in state to generate response.")
                if self._logger:
                    self._logger.log("ERROR", "No question in state to generate response")
                error_msg = "Could not generate a response as the question is missing."
                ai_message = AIMessage(content=error_msg)
                return {"response": error_msg, "messages": [ai_message]}

            if not datasource:
                print("No datasource selected to generate response.")
                if self._logger:
                    self._logger.log("ERROR", "No datasource selected to generate response")
                error_msg = "Could not generate a response as the data source is missing."
                ai_message = AIMessage(content=error_msg)
                return {"response": error_msg, "messages": [ai_message]}

            if not relevant_context:
                print("No relevant context found to generate response.")
                if self._logger:
                    self._logger.log("WARNING", "No relevant context found to generate response")
                error_msg = "I found no relevant information to answer your question based on the available documents."
                ai_message = AIMessage(content=error_msg)
                return {"response": error_msg, "messages": [ai_message]}

            datasource_config = next((d for d in self._config.datasources if d.name == datasource), None)
            if not datasource_config:
                print(f"Datasource configuration for '{datasource}' not found.")
                if self._logger:
                    self._logger.log("ERROR", f"Datasource configuration for '{datasource}' not found")
                error_msg = "Configuration error: Cannot generate response."
                ai_message = AIMessage(content=error_msg)
                return {"response": error_msg, "messages": [ai_message]}

            try:
                template = datasource_config.prompt_templates.rag_prompt
                combined_context = "\n\n".join(relevant_context)
                system_prompt_content = template.format(context=combined_context, question=question)

                # Log generation details
                if self._logger:
                    self._logger.log("INFO", "Generating RAG response", {
                        "datasource": datasource,
                        "num_relevant_docs": len(relevant_context),
                        "context_length": len(combined_context),
                        "question": question
                    })

                messages_for_llm = [SystemMessage(content=system_prompt_content)] + messages
                response_ai = self._model.invoke(messages_for_llm)
                print(f"Response generated using '{datasource}' with {len(relevant_context)} relevant docs.")

                return {"response": response_ai.content, "messages": [response_ai]}

            except Exception as e:
                print(f"Error generating RAG response: {str(e)}")
                if self._logger:
                    import traceback
                    self._logger.log_error("ResponseGenerationError", str(e), traceback.format_exc())
                error_msg = "I encountered an error while formulating the response."
                ai_message = AIMessage(content=error_msg)
                return {"response": error_msg, "messages": [ai_message]}

    @property
    def prompt(self) -> Any:
        return None

    @property
    def model(self) -> Any:
        return self._model

    @property
    def retrievers(self) -> Dict[str, Any]:
        return self._retrievers