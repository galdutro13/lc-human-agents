# source/rag/functions/response.py
from typing import Dict, Any

from langchain_core.messages import SystemMessage, AIMessage
from langchain_community.vectorstores import Chroma

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig
from source.rag.state.rag_state import RAGState

class RAGResponseFunction(ChatFunction):
    """
    Generates responses from relevant documents.
    Implements the ChatFunction interface for compatibility with the existing system.
    """
    def __init__(self, config: RAGConfig, vectorstores: Dict[str, Chroma], model: Any):
        self._config = config
        self._vectorstores = vectorstores
        self._model = model
        self._retrievers = {}
        self._initialize_retrievers()

    def _initialize_retrievers(self):
        for datasource_name, vectorstore in self._vectorstores.items():
            datasource = next((d for d in self._config.datasources if d.name == datasource_name), None)
            if not datasource: continue
            retriever_config = datasource.retriever_config
            retriever_kwargs = {"search_type": retriever_config.search_type, "search_kwargs": {}}
            if retriever_config.top_k: retriever_kwargs["search_kwargs"]["k"] = retriever_config.top_k
            if retriever_config.search_type == "mmr" and retriever_config.fetch_k: retriever_kwargs["search_kwargs"]["fetch_k"] = retriever_config.fetch_k
            if retriever_config.search_type == "mmr" and retriever_config.lambda_mult: retriever_kwargs["search_kwargs"]["lambda_mult"] = retriever_config.lambda_mult
            if retriever_config.score_threshold: retriever_kwargs["search_kwargs"]["score_threshold"] = retriever_config.score_threshold
            self._retrievers[datasource_name] = vectorstore.as_retriever(**retriever_kwargs)

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Generates a response based on relevant documents.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary updating the state with the generated response and messages
        """
        print("---GENERATE RESPONSE FROM RELEVANT DOCS---")

        # Acesso via dicionário com defaults
        question = state.get('question')
        datasource = state.get('datasource')
        relevant_context = state.get('relevant_context', [])
        messages = state.get('messages', []) # Obtém mensagens existentes

        # Validações
        if not question:
            print("No question in state to generate response.")
            error_msg = "Could not generate a response as the question is missing."
            ai_message = AIMessage(content=error_msg)
            return {"response": error_msg, "messages": [ai_message]} # Atualização parcial

        if not datasource:
            print("No datasource selected to generate response.")
            error_msg = "Could not generate a response as the data source is missing."
            ai_message = AIMessage(content=error_msg)
            return {"response": error_msg, "messages": [ai_message]} # Atualização parcial

        if not relevant_context:
            print("No relevant context found to generate response.")
            # Este caso teoricamente não deveria ocorrer devido ao nó condicional,
            # mas é bom ter um fallback.
            error_msg = "I found no relevant information to answer your question based on the available documents."
            ai_message = AIMessage(content=error_msg)
            return {"response": error_msg, "messages": [ai_message]} # Atualização parcial

        datasource_config = next((d for d in self._config.datasources if d.name == datasource), None)
        if not datasource_config:
            print(f"Datasource configuration for '{datasource}' not found.")
            error_msg = "Configuration error: Cannot generate response."
            ai_message = AIMessage(content=error_msg)
            return {"response": error_msg, "messages": [ai_message]} # Atualização parcial

        try:
            template = datasource_config.prompt_templates.rag_prompt
            combined_context = "\n\n".join(relevant_context)
            system_prompt_content = template.format(context=combined_context, question=question)

            # Prepara as mensagens para o LLM: prompt do sistema + histórico
            # O add_messages cuidará de adicionar a resposta do AI corretamente
            messages_for_llm = [SystemMessage(content=system_prompt_content)] + messages

            response_ai = self._model.invoke(messages_for_llm)
            print(f"Response generated using '{datasource}' with {len(relevant_context)} relevant docs.")

            # Retorna atualização parcial: a resposta e a nova mensagem AI
            return {"response": response_ai.content, "messages": [response_ai]}

        except Exception as e:
            print(f"Error generating RAG response: {str(e)}")
            error_msg = "I encountered an error while formulating the response."
            ai_message = AIMessage(content=error_msg)
            # Retorna atualização parcial
            return {"response": error_msg, "messages": [ai_message]}

    @property
    def prompt(self) -> Any:
        return None # Não usa um ChatPromptTemplate diretamente aqui

    @property
    def model(self) -> Any:
        return self._model

    @property
    def retrievers(self) -> Dict[str, Any]:
        return self._retrievers