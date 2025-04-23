# source/rag/functions/grader.py
from typing import Dict, Any
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate

from source.chat_graph.chat_function import ChatFunction
from source.rag.config.models import RAGConfig
from source.rag.state.rag_state import RAGState

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