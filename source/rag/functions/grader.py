# source/rag/functions/grader.py (MODIFIED)
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig
from source.rag.state.rag_state import RAGState
from source.rag.logging.rag_logger import RAGLogger, rag_function_logger


class GraderFunction(ChatFunction):
    """
    Grades the relevance of retrieved documents.
    Implements the ChatFunction interface for compatibility with the existing system.
    """

    def __init__(self, config: RAGConfig, model: Any, logger: Optional[RAGLogger] = None):
        self._config = config
        self._model = model
        self._prompt = self._create_grader_prompt()
        self._logger = logger

    def __call__(self, state: RAGState) -> Dict[str, Any]:
        """
        Grades the relevance of each retrieved document separately.

        Args:
            state: Current state of the workflow (RAGState TypedDict)

        Returns:
            Partial dictionary updating relevance assessment and relevant documents
        """
        with rag_function_logger(self._logger, "GraderFunction", state):
            print("---GRADE DOCUMENTS---")

            # Acesso via dicionário
            context = state.get('context', [])
            question = state.get('question')

            # Validações iniciais
            if not context or not question:
                print("No context or question in state for grading.")
                if self._logger:
                    self._logger.log("WARNING", "No context or question for grading",
                                     {"has_context": bool(context), "has_question": bool(question)})
                return {"documents_relevant": False, "relevant_context": []}

            if all(not doc.strip() for doc in context):
                print("All context documents are empty. Grading as not relevant.")
                if self._logger:
                    self._logger.log("WARNING", "All context documents are empty")
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
            document_grades = []

            try:
                for idx, document in enumerate(context):
                    if not document or not document.strip():
                        print(f"Document {idx + 1} is empty, skipping grade.")
                        document_grades.append({
                            "index": idx,
                            "relevant": False,
                            "reason": "empty_document"
                        })
                        continue

                    result = grader_chain.invoke({"question": question, "document": document})
                    is_relevant = result.binary_score.lower() == "yes"
                    print(f"Document {idx + 1} relevance: {'YES' if is_relevant else 'NO'}")

                    document_grades.append({
                        "index": idx,
                        "relevant": is_relevant,
                        "document_preview": document[:100] + "..." if len(document) > 100 else document
                    })

                    if is_relevant:
                        relevant_documents.append(document)

                documents_relevant = len(relevant_documents) > 0
                print(f"Grading complete: {len(relevant_documents)} relevant documents found.")

                # Log grading results
                if self._logger:
                    self._logger.log_grading(document_grades)

                return {
                    "documents_relevant": documents_relevant,
                    "relevant_context": relevant_documents
                }

            except Exception as e:
                print(f"Error grading documents: {str(e)}")
                if self._logger:
                    import traceback
                    self._logger.log_error("GradingError", str(e), traceback.format_exc())
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