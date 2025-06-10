# source/rag/functions/router.py (MODIFIED)
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig
from source.rag.state.rag_state import RAGState
from source.rag.logging.rag_logger import RAGLogger, rag_function_logger


class RouterFunction(ChatFunction):
    """
    Routes queries to the appropriate datasource.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, config: RAGConfig, datasource_names: List[str], model: Any,
                 logger: Optional[RAGLogger] = None):
        self._config = config
        self._datasource_names = datasource_names
        self._model = model
        self._prompt = self._create_router_prompt()
        self._logger = logger

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Routes the query to the appropriate datasource.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary to update the state with the selected datasource and messages
        """
        with rag_function_logger(self._logger, "RouterFunction", state):
            print("---ROUTE QUERY---")

            # Acesso via dicionário
            question = state.get('question')

            # Garante que a questão existe
            if not question:
                print("No question provided in state for routing.")
                if self._logger:
                    self._logger.log("WARNING", "No question provided for routing")
                first_datasource = self._datasource_names[0] if self._datasource_names else None
                return {"datasource": first_datasource, "messages": []}

            # Cria a mensagem humana uma vez
            human_message = HumanMessage(content=question)

            # Verifica se há datasources disponíveis
            if not self._datasource_names:
                print("No datasources available for routing.")
                if self._logger:
                    self._logger.log("WARNING", "No datasources available for routing")
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
                    if self._logger:
                        self._logger.log("WARNING",
                                         f"LLM selected unavailable datasource '{selected_datasource}'",
                                         {"available": self._datasource_names})
                    selected_datasource = self._datasource_names[0]
                else:
                    print(f"Query routed to datasource: {selected_datasource}")

                # Log routing decision
                if self._logger:
                    self._logger.log_routing_decision(selected_datasource)

                return {"datasource": selected_datasource, "messages": [human_message]}

            except Exception as e:
                print(f"Error routing query: {str(e)}")
                if self._logger:
                    import traceback
                    self._logger.log_error("RouterError", str(e), traceback.format_exc())

                # Fallback em caso de erro
                first_datasource = self._datasource_names[0]
                print(f"Using default datasource due to error: {first_datasource}")
                return {"datasource": first_datasource, "messages": [human_message]}

    def _create_router_prompt(self) -> ChatPromptTemplate:
        datasource_descriptions = []
        for ds_name in self._datasource_names:
            datasource = next((d for d in self._config.datasources if d.name == ds_name), None)
            if datasource:
                datasource_descriptions.append(
                    f"- '{ds_name}': {datasource.description or 'No description available.'}")
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