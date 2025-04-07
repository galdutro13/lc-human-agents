from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_community.vectorstores import Chroma

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig
from source.rag.state.rag_state import RAGState


class RetrieveFunction(ChatFunction):
    """
    Retrieves documents from the selected datasource.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, retrievers: Dict[str, Any]):
        """
        Initializes the RetrieveFunction.

        Args:
            retrievers: Dictionary of retrievers by datasource
        """
        self._retrievers = retrievers

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Retrieves documents from the selected datasource.

        Args:
            state: Current state of the workflow (RAGState)

        Returns:
            Updated state with the retrieved documents
        """
        print("---RETRIEVE FROM DATASOURCE---")

        # Get the datasource from the state
        datasource = state.datasource
        question = state.question

        # Check if datasource is available
        if not datasource or datasource not in self._retrievers:
            # Fallback to the first available datasource
            datasource = next(iter(self._retrievers.keys()), None)
            if not datasource:
                print("No datasources available")
                return {"context": []}

            print(f"Datasource '{state.datasource}' not available, using '{datasource}' as fallback")

        # Retrieve documents
        try:
            retriever = self._retrievers[datasource]
            docs = retriever.invoke(question)
            print(f"Retrieved {len(docs)} documents from datasource '{datasource}'")

            # Extract document content
            context = [doc.page_content for doc in docs]
            return {"context": context}

        except Exception as e:
            print(f"Error retrieving documents: {str(e)}")
            return {"context": []}

    @property
    def prompt(self) -> Any:
        """
        Gets the prompt used by the function.

        Returns:
            None as no prompt is used
        """
        return None

    @property
    def model(self) -> Any:
        """
        Gets the model used by the function.

        Returns:
            None as no model is used
        """
        return None


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

    def __call__(self, state: 'RAGState') -> Dict[str, Any]:
        """
        Routes the query to the appropriate datasource.

        Args:
            state: Current state of the workflow (RAGState)

        Returns:
            Updated state with the selected datasource
        """
        print("---ROUTE QUERY---")

        # Add the user's question as a human message
        human_message = HumanMessage(content=state.question)

        # Check if there are available datasources
        if not self._datasource_names:
            print("No datasources available")
            return {"datasource": None, "messages": [human_message]}

        # Get the question from the state
        question = state.question
        if not question:
            print("No question in state")
            print(f"Using default datasource: {self._datasource_names[0]}")
            return {"datasource": self._datasource_names[0], "messages": [human_message]}

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
            selected_datasource = result.datasource
            if selected_datasource not in self._datasource_names:
                # If not available, use the first datasource
                print(f"Datasource {selected_datasource} not found. Using: {self._datasource_names[0]}")
                selected_datasource = self._datasource_names[0]
            else:
                print(f"Selected datasource: {selected_datasource}")

            return {"datasource": selected_datasource, "messages": [human_message]}

        except Exception as e:
            print(f"Error routing query: {str(e)}")
            # In case of error, use the first datasource
            first_datasource = self._datasource_names[0]
            print(f"Using default datasource: {first_datasource}")
            return {"datasource": first_datasource, "messages": [human_message]}

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

    def __call__(self, state: 'RAGState') -> Dict[str, Any]:
        """
        Grades the relevance of each retrieved document separately.

        Args:
            state: Current state of the workflow (RAGState)

        Returns:
            Updated state with the relevance assessment and relevant documents
        """
        print("---GRADE DOCUMENTS---")

        # Get the context and question from the state
        context = state.context
        question = state.question

        # If no context or question, documents are not relevant
        if not context or not question:
            print("No context or question in state. Documents not relevant.")
            return {
                "documents_relevant": False,
                "relevant_context": []
            }

        # If all contexts are empty, documents are not relevant
        if all(not doc.strip() for doc in context):
            print("All context documents are empty. Documents not relevant.")
            return {
                "documents_relevant": False,
                "relevant_context": []
            }

        # Define the grading model
        class GradeDocuments(BaseModel):
            binary_score: str = Field(
                ...,
                description="Document is relevant to the question, 'yes' or 'no'"
            )

        # Create a structured output model
        structured_grader = self._model.with_structured_output(GradeDocuments)

        # Combine prompt and model
        grader_chain = self._prompt | structured_grader

        relevant_documents = []
        grading_results = []

        try:
            # Grade each document separately
            for idx, document in enumerate(context):
                if not document.strip():
                    continue  # Skip empty documents

                # Invoke the grader for this document
                result = grader_chain.invoke({
                    "question": question,
                    "document": document
                })

                # Check the result
                is_relevant = result.binary_score.lower() == "yes"
                grading_results.append(is_relevant)

                if is_relevant:
                    relevant_documents.append(document)
                    print(f"Document {idx + 1} is relevant")
                else:
                    print(f"Document {idx + 1} is not relevant")

            # Check if we have any relevant documents
            documents_relevant = len(relevant_documents) > 0
            print(f"Found {len(relevant_documents)} relevant documents out of {len(context)}")

            return {
                "documents_relevant": documents_relevant,
                "relevant_context": relevant_documents
            }

        except Exception as e:
            print(f"Error grading documents: {str(e)}")
            # In case of error, assume documents are not relevant
            return {
                "documents_relevant": False,
                "relevant_context": []
            }

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
        self._retrievers = {}  # Store retrievers separately

        # Initialize retrievers
        self._initialize_retrievers()

    def _initialize_retrievers(self):
        """
        Initializes retrievers for each datasource based on configuration.
        """
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

            # Create and store the retriever
            retriever = vectorstore.as_retriever(**retriever_kwargs)
            self._retrievers[datasource_name] = retriever

    def __call__(self, state: 'RAGState') -> Dict[str, Any]:
        """
        Generates a response based on relevant documents.

        Args:
            state: Current state of the workflow (RAGState)

        Returns:
            Updated state with the generated response
        """
        print("---GENERATE RESPONSE FROM RELEVANT DOCS---")

        # Get the question, datasource, and relevant documents from the state
        question = state.question
        datasource = state.datasource
        relevant_context = state.relevant_context  # Use relevant_context instead of all context

        # If no question or datasource, return empty response
        if not question or not datasource:
            print("No question or datasource in state")
            error_msg = "I don't have enough information to answer that question."

            # Create an AI message with the error response
            ai_message = AIMessage(
                content=error_msg
            )

            return {"response": error_msg, "messages": [ai_message]}

        # If no relevant documents, return empty response
        if not relevant_context:
            print("No relevant documents in state")
            error_msg = "I don't have relevant information to answer that question."

            # Create an AI message with the error response
            ai_message = AIMessage(
                content=error_msg
            )

            return {"response": error_msg, "messages": [ai_message]}

        # Check if the datasource is available and get config
        datasource_config = next((d for d in self._config.datasources if d.name == datasource), None)
        if not datasource_config:
            print(f"Datasource configuration for {datasource} not found")
            error_msg = "I don't have the information needed to answer that question."

            # Create an AI message with the error response
            ai_message = AIMessage(
                content=error_msg
            )

            return {"response": error_msg, "messages": [ai_message]}

        # Use relevant context with the RAG prompt template
        try:
            # Get the prompt template from datasource config
            template = datasource_config.prompt_templates.rag_prompt

            # Combine relevant documents
            combined_context = "\n\n".join(relevant_context)

            # Create a system message with the context and prompt
            system_prompt = template.format(context=combined_context, question=question)

            # Create messages for the model (system message + existing messages)
            messages = [SystemMessage(content=system_prompt)] + state.messages

            # Invoke the model directly
            response = self._model.invoke(messages)

            print(f"Response generated using datasource '{datasource}' with {len(relevant_context)} relevant documents")

            return {"response": response.content, "messages": [response]}

        except Exception as e:
            print(f"Error generating response: {str(e)}")
            error_msg = "I encountered an error while trying to answer your question."

            # Create an AI message with the error response
            ai_message = AIMessage(
                content=error_msg
            )

            return {"response": error_msg, "messages": [ai_message]}

    @property
    def prompt(self) -> Any:
        """
        Gets the prompt used by the function.

        Returns:
            None as we're using direct model invocation
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

    @property
    def retrievers(self) -> Dict[str, Any]:
        """
        Gets the retrievers by datasource.

        Returns:
            Dictionary of retrievers by datasource
        """
        return self._retrievers


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

    def __call__(self, state: 'RAGState') -> Dict[str, Any]:
        """
        Generates a fallback response when documents are not relevant.

        Args:
            state: Current state of the workflow (RAGState)

        Returns:
            Updated state with the fallback response
        """
        print("---HANDLE IRRELEVANT DOCUMENTS---")

        # Get the question from the state
        question = state.question

        # If no question, return generic response
        if not question:
            generic_response = "I don't have enough information to answer that question."

            # Create an AI message with the generic response
            ai_message = AIMessage(
                content=generic_response
            )

            return {"response": generic_response, "messages": ai_message}

        # Generate fallback response
        try:
            # Create a system message for fallback
            system_prompt = """You are a helpful assistant. The user's question is outside the scope 
            of our knowledge base or we don't have relevant information about it.

            Please provide a polite response indicating that we don't have enough 
            information about this specific topic, but offer some general guidance 
            if possible."""

            # Use all existing messages + system prompt for context
            messages = [SystemMessage(content=system_prompt)] + state.messages

            # Invoke the model directly
            response = self._model.invoke(messages)

            print("Fallback response generated")

            return {"response": response.content, "messages": response}

        except Exception as e:
            print(f"Error generating fallback response: {str(e)}")
            error_response = "I don't have the information needed to answer that question."

            # Create an AI message with the error response
            ai_message = AIMessage(
                content=error_response
            )

            return {"response": error_response, "messages": [ai_message]}

    @property
    def prompt(self) -> Any:
        """
        Gets the prompt used by the function.

        Returns:
            None as we're not using a prompt template anymore
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