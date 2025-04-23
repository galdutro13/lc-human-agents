# source/rag/functions/retrieve.py
from typing import Dict, Any

from source.chat_graph.chat_function import ChatFunction
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