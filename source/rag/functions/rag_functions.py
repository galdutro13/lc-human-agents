# source/rag/functions/rag_functions.py
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field # Mantido para os modelos de saída estruturada

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_community.vectorstores import Chroma

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig
# Importa o RAGState refatorado
from source.rag.state.rag_state import RAGState


class RetrieveFunction(ChatFunction):
    """
    Retrieves documents from the selected datasource.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, retrievers: Dict[str, Any]):
        self._retrievers = retrievers

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Retrieves documents from the selected datasource.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary to update the state with retrieved documents
        """
        print("---RETRIEVE FROM DATASOURCE---")

        # Acesso via dicionário
        datasource = state.get('datasource')
        question = state.get('question')

        # Verifica se a datasource foi definida
        if not datasource or datasource not in self._retrievers:
            print(f"Datasource '{datasource}' not found or not selected.")
            # Fallback para a primeira datasource disponível, se houver
            if self._retrievers:
                datasource = next(iter(self._retrievers.keys()))
                print(f"Falling back to the first available datasource: '{datasource}'")
            else:
                print("No datasources available to retrieve from.")
                return {"context": []} # Retorna atualização parcial

        # Verifica se a questão foi definida
        if not question:
            print("No question found in state.")
            return {"context": []} # Retorna atualização parcial

        try:
            retriever = self._retrievers[datasource]
            docs = retriever.invoke(question)
            print(f"Retrieved {len(docs)} documents from datasource '{datasource}' for question: '{question[:50]}...'")

            context = [doc.page_content for doc in docs]
            # Retorna apenas o campo 'context' para atualização
            return {"context": context}

        except Exception as e:
            print(f"Error retrieving documents from '{datasource}': {str(e)}")
            # Retorna atualização parcial com contexto vazio em caso de erro
            return {"context": []}

    @property
    def prompt(self) -> Any:
        return None

    @property
    def model(self) -> Any:
        return None


class RouterFunction(ChatFunction):
    """
    Routes queries to the appropriate datasource.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, config: RAGConfig, datasource_names: List[str], model: Any):
        self._config = config
        self._datasource_names = datasource_names
        self._model = model
        self._prompt = self._create_router_prompt()

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Routes the query to the appropriate datasource.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary to update the state with the selected datasource and messages
        """
        print("---ROUTE QUERY---")

        # Acesso via dicionário
        question = state.get('question')

        # Garante que a questão existe
        if not question:
            print("No question provided in state for routing.")
            # Pode retornar um erro ou um estado padrão, dependendo da lógica desejada
            # Aqui, retornaremos um estado indicando falha ou usando default
            first_datasource = self._datasource_names[0] if self._datasource_names else None
            return {"datasource": first_datasource, "messages": []} # Atualização parcial

        # Cria a mensagem humana uma vez
        human_message = HumanMessage(content=question)

        # Verifica se há datasources disponíveis
        if not self._datasource_names:
            print("No datasources available for routing.")
            # Retorna atualização parcial
            return {"datasource": None, "messages": [human_message]}

        # Lógica de roteamento
        try:
            class DynamicRouteQuery(BaseModel):
                datasource: str = Field(
                    ...,
                    description="Choose the most relevant datasource for the query"
                )

            structured_router = self._model.with_structured_output(DynamicRouteQuery)
            router_chain = self._prompt | structured_router
            result = router_chain.invoke({"question": question})
            selected_datasource = result.datasource

            # Validação se a datasource selecionada existe
            if selected_datasource not in self._datasource_names:
                print(f"LLM selected unavailable datasource '{selected_datasource}'. Falling back.")
                selected_datasource = self._datasource_names[0] # Fallback
            else:
                print(f"Query routed to datasource: {selected_datasource}")

            # Retorna atualização parcial
            return {"datasource": selected_datasource, "messages": [human_message]}

        except Exception as e:
            print(f"Error routing query: {str(e)}")
            # Fallback em caso de erro
            first_datasource = self._datasource_names[0]
            print(f"Using default datasource due to error: {first_datasource}")
            # Retorna atualização parcial
            return {"datasource": first_datasource, "messages": [human_message]}

    def _create_router_prompt(self) -> ChatPromptTemplate:
        datasource_descriptions = []
        for ds_name in self._datasource_names:
            datasource = next((d for d in self._config.datasources if d.name == ds_name), None)
            if datasource:
                datasource_descriptions.append(f"- '{ds_name}': {datasource.description or 'No description available.'}")
        datasource_desc_str = "\n".join(datasource_descriptions)

        router_system_prompt = self._config.global_prompts.router_prompt
        if "{datasource_descriptions}" not in router_system_prompt:
            router_system_prompt += "\n\nAvailable datasources:\n{datasource_descriptions}"
        router_system_prompt = router_system_prompt.replace("{datasource_descriptions}", datasource_desc_str)

        return ChatPromptTemplate.from_messages([
            ("system", router_system_prompt),
            ("human", "{question}"),
        ])

    @property
    def prompt(self) -> Any:
        return self._prompt

    @property
    def model(self) -> Any:
        return self._model


class GraderFunction(ChatFunction):
    """
    Grades the relevance of retrieved documents.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, config: RAGConfig, model: Any):
        self._config = config
        self._model = model
        self._prompt = self._create_grader_prompt()

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Grades the relevance of each retrieved document separately.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary updating relevance assessment and relevant documents
        """
        print("---GRADE DOCUMENTS---")

        # Acesso via dicionário
        context = state.get('context', []) # Usa .get com default
        question = state.get('question')

        # Validações iniciais
        if not context or not question:
            print("No context or question in state for grading.")
            # Retorna atualização parcial
            return {"documents_relevant": False, "relevant_context": []}
        if all(not doc.strip() for doc in context):
            print("All context documents are empty. Grading as not relevant.")
             # Retorna atualização parcial
            return {"documents_relevant": False, "relevant_context": []}

        # Modelo de saída para o grader
        class GradeDocuments(BaseModel):
            binary_score: str = Field(
                ...,
                description="Document is relevant to the question, 'yes' or 'no'"
            )
        structured_grader = self._model.with_structured_output(GradeDocuments)
        grader_chain = self._prompt | structured_grader

        relevant_documents = []
        try:
            for idx, document in enumerate(context):
                if not document or not document.strip(): # Pula documentos vazios
                    print(f"Document {idx + 1} is empty, skipping grade.")
                    continue

                result = grader_chain.invoke({"question": question, "document": document})
                is_relevant = result.binary_score.lower() == "yes"
                print(f"Document {idx + 1} relevance: {'YES' if is_relevant else 'NO'}")
                if is_relevant:
                    relevant_documents.append(document)

            documents_relevant = len(relevant_documents) > 0
            print(f"Grading complete: {len(relevant_documents)} relevant documents found.")

            # Retorna atualização parcial
            return {
                "documents_relevant": documents_relevant,
                "relevant_context": relevant_documents
            }

        except Exception as e:
            print(f"Error grading documents: {str(e)}")
             # Retorna atualização parcial em caso de erro
            return {"documents_relevant": False, "relevant_context": []}

    def _create_grader_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", self._config.global_prompts.grader_prompt),
            ("human", "Retrieved document: \n\n {document} \n\n User question: {question}"),
        ])

    @property
    def prompt(self) -> Any:
        return self._prompt

    @property
    def model(self) -> Any:
        return self._model


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
            # print(response_ai)
            # print(messages)
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
        messages = state.get('messages', []) # Obtém histórico de mensagens

        if not question:
            print("No question in state for fallback.")
            generic_response = "I cannot provide an answer as the question is missing."
            ai_message = AIMessage(content=generic_response)
            return {"response": generic_response, "messages": [ai_message]} # Atualização parcial

        try:
            # Prompt para o LLM gerar uma resposta genérica/educada
            system_prompt = """You are a helpful assistant. The user asked a question, but the retrieved documents were not relevant or helpful to answer it.
            Please provide a polite response stating that you couldn't find specific information in the knowledge base for this question.
            Avoid making up information. You can offer general assistance if appropriate."""

            # Prepara mensagens para o LLM: prompt do sistema + histórico
            messages_for_llm = [SystemMessage(content=system_prompt)] + messages

            response_ai = self._model.invoke(messages_for_llm)
            # print(response_ai)
            # print(messages)
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