# source/rag/functions/rewrite_query.py (MODIFIED)
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig
from source.rag.state.rag_state import RAGState
from source.rag.logging.rag_logger import RAGLogger, rag_function_logger

class RewriteQueryFunction(ChatFunction):
    """
    Rewrites the original query into multiple improved versions.
    """

    def __init__(self, config: RAGConfig, model: Any, logger: Optional[RAGLogger] = None):
        self._config = config
        self._model = model
        self._prompt = self._create_rewrite_prompt()
        self._logger = logger

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Rewrites the original query into multiple improved versions.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary updating the state with rewritten queries
        """
        with rag_function_logger(self._logger, "RewriteQueryFunction", state):
            print("---REWRITE QUERY---")

            # Access via dictionary
            question = state.get('question')

            if not question:
                print("No question provided in state for rewriting.")
                if self._logger:
                    self._logger.log("WARNING", "No question provided for rewriting")
                return {
                    "original_question": "",
                    "rewritten_queries": [],
                    "current_query_index": 0,
                    "has_more_queries": False
                }

            try:
                # Invoke the LLM to rewrite the query
                rewrite_result = self._model.invoke([
                    SystemMessage(content=self._config.global_prompts.rewrite_query_prompt),
                    HumanMessage(content=question)
                ])

                # Parse the numbered list of rewritten queries
                rewritten_queries = []
                for line in rewrite_result.content.strip().split('\n'):
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith('- ')):
                        # Remove the number/bullet and any trailing/leading whitespace
                        query = line
                        if '.' in line and line[0].isdigit():
                            query = line.split('.', 1)[-1].strip()
                        elif line.startswith('- '):
                            query = line[2:].strip()
                        if query:
                            rewritten_queries.append(query)

                if not rewritten_queries:
                    # If parsing fails, use the raw output (might not be in expected format)
                    rewritten_queries = [rewrite_result.content.strip()]

                print(f"Original query: '{question}'")
                print(f"Rewrote into {len(rewritten_queries)} queries:")
                for i, q in enumerate(rewritten_queries):
                    print(f"  {i+1}. {q}")

                # Log query rewriting
                if self._logger:
                    self._logger.log_query_rewrite(question, rewritten_queries)

                # Return updated state with rewritten queries
                return {
                    "original_question": question,
                    "rewritten_queries": rewritten_queries,
                    "current_query_index": 0,
                    "has_more_queries": len(rewritten_queries) > 0
                }

            except Exception as e:
                print(f"Error rewriting query: {str(e)}")
                if self._logger:
                    import traceback
                    self._logger.log_error("QueryRewriteError", str(e), traceback.format_exc())
                # Return the original query as a fallback
                return {
                    "original_question": question,
                    "rewritten_queries": [question],
                    "current_query_index": 0,
                    "has_more_queries": True
                }

    def _create_rewrite_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", self._config.global_prompts.rewrite_query_prompt),
            ("human", "{question}"),
        ])

    @property
    def prompt(self) -> Any:
        return self._prompt

    @property
    def model(self) -> Any:
        return self._model