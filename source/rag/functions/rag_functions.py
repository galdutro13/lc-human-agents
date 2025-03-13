from typing import Dict, List, Any, Optional, Literal, Union, Tuple
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import Chroma

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig


class RouterFunction(ChatFunction):
    """
    Routes queries to the appropriate datasource.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, config: RAGConfig, datasource_names: List[str], model: Any):
        """
        Initializes the RouterFunction.

        Args:
            config: RAG system configuration
            datasource_names: List of available datasource names
            model: Language model to use for routing
        """
        self._config = config
        self._datasource_names = datasource_names
        self._model = model
        self._prompt = self._create_router_prompt()

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes the query to the appropriate datasource.

        Args:
            state: Current state of the workflow

        Returns:
            Updated state with the selected datasource
        """
        print("---ROUTE QUERY---")

        # Check if there are available datasources
        if not self._datasource_names:
            print("No datasources available")
            return {"datasource": None}

        # Get the question from the state
        question = state.get("question")
        if not question:
            print("No question in state")
            return {"datasource": self._datasource_names[0]}

        # Try to route the query
        try:
            # Create a routing model that only accepts the available datasources
            class DynamicRouteQuery(BaseModel):
                datasource: str = Field(
                    ...,
                    description="Choose the most relevant datasource for the query"
                )

            # Create a structured output model
            structured_router = self._model.with_structured_output(DynamicRouteQuery)

            # Combine prompt and model
            router_chain = self._prompt | structured_router

            # Invoke the router
            result = router_chain.invoke({"question": question})

            # Check if the datasource is available
            if result.datasource in self._datasource_names:
                print(f"Selected datasource: {result.datasource}")
                return {"datasource": result.datasource}
            else:
                # If not available, use the first datasource
                print(f"Datasource {result.datasource} not found. Using: {self._datasource_names[0]}")
                return {"datasource": self._datasource_names[0]}

        except Exception as e:
            print(f"Error routing query: {str(e)}")
            # In case of error, use the first datasource
            print(f"Using default datasource: {self._datasource_names[0]}")
            return {"datasource": self._datasource_names[0]}

    def _create_router_prompt(self) -> ChatPromptTemplate:
        """
        Creates the prompt for routing queries.

        Returns:
            ChatPromptTemplate for routing
        """
        # Prepare descriptions of available datasources
        datasource_descriptions = []
        for ds_name in self._datasource_names:
            datasource = next((d for d in self._config.datasources if d.name == ds_name), None)
            if datasource:
                datasource_descriptions.append(f"- '{ds_name}': {datasource.description}")

        datasource_desc_str = "\n".join(datasource_descriptions)

        # Create a customized prompt based on the router_prompt in the configuration
        router_system_prompt = self._config.global_prompts.router_prompt
        if "{datasource_descriptions}" not in router_system_prompt:
            router_system_prompt += "\n\nAvailable datasources:\n{datasource_descriptions}"

        router_system_prompt = router_system_prompt.replace("{datasource_descriptions}", datasource_desc_str)

        # Create and return the prompt
        return ChatPromptTemplate.from_messages([
            ("system", router_system_prompt),
            ("human", "{question}"),
        ])

    @property
    def prompt(self) -> Any:
        """
        Gets the prompt used by the function.

        Returns:
            The routing prompt
        """
        return self._prompt

    @property
    def model(self) -> Any:
        """
        Gets the model used by the function.

        Returns:
            The language model
        """
        return self._model


class GraderFunction(ChatFunction):
    """
    Grades the relevance of retrieved documents.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, config: RAGConfig, model: Any):
        """
        Initializes the GraderFunction.

        Args:
            config: RAG system configuration
            model: Language model to use for grading
        """
        self._config = config
        self._model = model
        self._prompt = self._create_grader_prompt()

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Grades the relevance of the retrieved documents.

        Args:
            state: Current state of the workflow

        Returns:
            Updated state with the relevance assessment
        """
        print("---GRADE DOCUMENTS---")

        # Get the context and question from the state
        context = state.get("context", [])
        question = state.get("question")

        # If no context or question, documents are not relevant
        if not context or not question:
            print("No context or question in state. Documents not relevant.")
            return {"documents_relevant": False}

        # Combine the context for evaluation
        combined_context = "\n\n".join(context)

        # If the combined context is empty, documents are not relevant
        if not combined_context.strip():
            print("Empty context. Documents not relevant.")
            return {"documents_relevant": False}

        try:
            # Define the grading model
            class GradeDocuments(BaseModel):
                binary_score: str = Field(
                    ...,
                    description="Documents are relevant to the question, 'yes' or 'no'"
                )

            # Create a structured output model
            structured_grader = self._model.with_structured_output(GradeDocuments)

            # Combine prompt and model
            grader_chain = self._prompt | structured_grader

            # Invoke the grader
            result = grader_chain.invoke({
                "question": question,
                "document": combined_context
            })

            # Check the result
            is_relevant = result.binary_score.lower() == "yes"
            print(f"Documents are relevant: {is_relevant}")

            return {"documents_relevant": is_relevant}

        except Exception as e:
            print(f"Error grading documents: {str(e)}")
            # In case of error, assume documents are not relevant
            return {"documents_relevant": False}

    def _create_grader_prompt(self) -> ChatPromptTemplate:
        """
        Creates the prompt for grading document relevance.

        Returns:
            ChatPromptTemplate for grading
        """
        return ChatPromptTemplate.from_messages([
            ("system", self._config.global_prompts.grader_prompt),
            ("human", "Retrieved document: \n\n {document} \n\n User question: {question}"),
        ])

    @property
    def prompt(self) -> Any:
        """
        Gets the prompt used by the function.

        Returns:
            The grading prompt
        """
        return self._prompt

    @property
    def model(self) -> Any:
        """
        Gets the model used by the function.

        Returns:
            The language model
        """
        return self._model


class RAGResponseFunction(ChatFunction):
    """
    Generates responses from relevant documents.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, config: RAGConfig, vectorstores: Dict[str, Chroma], model: Any):
        """
        Initializes the RAGResponseFunction.

        Args:
            config: RAG system configuration
            vectorstores: Dictionary of vector stores by datasource
            model: Language model to use for response generation
        """
        self._config = config
        self._vectorstores = vectorstores
        self._model = model
        self._rag_chains = self._create_rag_chains()

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a response based on relevant documents.

        Args:
            state: Current state of the workflow

        Returns:
            Updated state with the generated response
        """
        print("---GENERATE RESPONSE FROM RELEVANT DOCS---")

        # Get the question and datasource from the state
        question = state.get("question")
        datasource = state.get("datasource")

        # If no question or datasource, return empty response
        if not question or not datasource:
            print("No question or datasource in state")
            return {"response": "I don't have enough information to answer that question."}

        # Check if the datasource is available
        if datasource not in self._rag_chains:
            # Fallback to the first available datasource
            datasource = next(iter(self._rag_chains.keys()), None)
            if not datasource:
                print("No datasources available")
                return {"response": "I don't have the information needed to answer that question."}

            print(f"Datasource '{datasource}' not available, using '{datasource}' instead")

        # Use the RAG chain to generate a response
        try:
            chain = self._rag_chains[datasource]
            response = chain.invoke({"question": question})
            print(f"Response generated using datasource '{datasource}'")

            return {"response": response}

        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return {"response": "I encountered an error while trying to answer your question."}

    def _create_rag_chains(self) -> Dict[str, Any]:
        """
        Creates RAG chains for each datasource.

        Returns:
            Dictionary of RAG chains by datasource
        """
        rag_chains = {}

        for datasource_name, vectorstore in self._vectorstores.items():
            # Get the datasource configuration
            datasource = next((d for d in self._config.datasources if d.name == datasource_name), None)
            if not datasource:
                continue

            # Configure the retriever
            retriever_config = datasource.retriever_config
            retriever_kwargs = {"search_type": retriever_config.search_type, "search_kwargs": {}}

            if retriever_config.top_k:
                retriever_kwargs["search_kwargs"]["k"] = retriever_config.top_k

            if retriever_config.search_type == "mmr" and retriever_config.fetch_k:
                retriever_kwargs["search_kwargs"]["fetch_k"] = retriever_config.fetch_k

            if retriever_config.search_type == "mmr" and retriever_config.lambda_mult:
                retriever_kwargs["search_kwargs"]["lambda_mult"] = retriever_config.lambda_mult

            if retriever_config.score_threshold:
                retriever_kwargs["search_kwargs"]["score_threshold"] = retriever_config.score_threshold

            retriever = vectorstore.as_retriever(**retriever_kwargs)

            # Create the prompt template
            template = datasource.prompt_templates.rag_prompt
            prompt = ChatPromptTemplate.from_template(template)

            # Define function to format documents
            def format_docs(docs):
                return "\n\n".join(doc.page_content for doc in docs)

            # Build the RAG chain
            rag_chain = (
                    {"context": lambda x: format_docs(retriever.invoke(x["question"])),
                     "question": lambda x: x["question"]}
                    | prompt
                    | self._model
                    | StrOutputParser()
            )

            # Store the chain
            rag_chains[datasource_name] = rag_chain

        return rag_chains

    @property
    def prompt(self) -> Any:
        """
        Gets the prompt used by the function. Not a single prompt in this case.

        Returns:
            None because multiple prompts are used
        """
        return None

    @property
    def model(self) -> Any:
        """
        Gets the model used by the function.

        Returns:
            The language model
        """
        return self._model


class FallbackFunction(ChatFunction):
    """
    Handles cases where no relevant documents are found.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, config: RAGConfig, model: Any):
        """
        Initializes the FallbackFunction.

        Args:
            config: RAG system configuration
            model: Language model to use for fallback responses
        """
        self._config = config
        self._model = model
        self._prompt = self._create_fallback_prompt()

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a fallback response when documents are not relevant.

        Args:
            state: Current state of the workflow

        Returns:
            Updated state with the fallback response
        """
        print("---HANDLE IRRELEVANT DOCUMENTS---")

        # Get the question from the state
        question = state.get("question")

        # If no question, return generic response
        if not question:
            return {"response": "I don't have enough information to answer that question."}

        # Generate fallback response
        try:
            # Combine prompt and model
            fallback_chain = self._prompt | self._model | StrOutputParser()

            # Invoke the chain
            response = fallback_chain.invoke({"question": question})
            print("Fallback response generated")

            return {"response": response}

        except Exception as e:
            print(f"Error generating fallback response: {str(e)}")
            return {"response": "I don't have the information needed to answer that question."}

    def _create_fallback_prompt(self) -> ChatPromptTemplate:
        """
        Creates the prompt for fallback responses.

        Returns:
            ChatPromptTemplate for fallback responses
        """
        return ChatPromptTemplate.from_template(
            """You are a helpful assistant. The user's question is outside the scope 
            of our knowledge base or we don't have relevant information about it.

            Question: {question}

            Please provide a polite response indicating that we don't have enough 
            information about this specific topic, but offer some general guidance 
            if possible."""
        )

    @property
    def prompt(self) -> Any:
        """
        Gets the prompt used by the function.

        Returns:
            The fallback prompt
        """
        return self._prompt

    @property
    def model(self) -> Any:
        """
        Gets the model used by the function.

        Returns:
            The language model
        """
        return self._model