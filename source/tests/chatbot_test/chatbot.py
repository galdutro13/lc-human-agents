import secrets
import sqlite3
from typing import Union, Optional

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from source.chat_graph import ModelName, ClassicChatFunction, ClassicWorkflowBuilder, get_llm
from source.prompt_manager.base import CustomSystemPromptStrategy

from source.rag.system import RAGSystem


class ChatBotBase:
    """
    Classe base para criação de chatbots. Configura o modelo, gera o prompt e
    constrói o fluxo de trabalho para processar interações com o usuário.
    """

    def __init__(
            self,
            think_exp: bool,
            system_message: str,
            use_sqlitesaver: bool = False,
            thread_id: Optional[str] = None
    ) -> None:
        """
        Inicializa o chatbot com base nos parâmetros fornecidos.

        :param think_exp: Define se o chatbot deve usar o modelo GEMINI_THINKING_EXP.
        :param system_message: Mensagem de contexto do sistema, utilizada no prompt inicial.
        :param use_sqlitesaver: Define se deve persistir mensagens em banco (SQLite).
        :param thread_id: ID único para rastreamento de sessão ou conversa.
        """
        self.think_exp = think_exp
        self.system_message = system_message
        # Gera um thread_id se não for fornecido
        self.thread_id = thread_id or secrets.token_hex(8)

        self.model = None
        self.prompt = None
        self.app = None
        self.config = None

        self.initialize(use_sqlitesaver)

    def initialize(self, use_sqlitesaver: bool) -> None:
        """
        Inicializa o chatbot, selecionando o modelo e definindo se
        as mensagens serão salvas em memória ou em banco de dados.
        """
        self.model = self._get_model(self.think_exp)
        self.prompt = CustomSystemPromptStrategy(
            prompt_template=self.system_message
        ).generate_prompt()

        memory_saver = self._get_memory_saver(use_sqlitesaver)
        self.app = ClassicWorkflowBuilder().build_classic_workflow(
            node_name="model",
            function=ClassicChatFunction(model=self.model, prompt=self.prompt),
            memory=memory_saver
        )

        self.config = {"configurable": {"thread_id": self.thread_id}}

    def _get_model(self, think_exp: bool):
        """
        Retorna o modelo apropriado baseado no valor de `think_exp`.
        """
        if think_exp:
            print(f"[{self.thread_id}] Usando GEMINI_THINKING_EXP")
            return get_llm(ModelName.GEMINI_THINKING_EXP)
        print(f"[{self.thread_id}] Usando GPT4_MINI")
        return get_llm(ModelName.GPT4)

    def _get_memory_saver(self, use_sqlitesaver: bool) -> Union[MemorySaver, SqliteSaver]:
        """
        Retorna o saver (Memory ou SQLite) baseado no valor de `use_sqlitesaver`.
        """
        if use_sqlitesaver:
            connection = sqlite3.connect("checkpoints.db", check_same_thread=False)
            return SqliteSaver(conn=connection)
        return MemorySaver()

    def process_query(self, query: str) -> str:
        """
        Processa a mensagem de um usuário e retorna a resposta do modelo.

        :param query: Texto enviado pelo usuário.
        :return: Texto de resposta gerado pelo modelo.
        """
        input_messages = [HumanMessage(query)]
        output = self.app.invoke({"messages": input_messages}, self.config)
        return output["messages"][-1].content

    async def aprocess_query(self, query: str) -> str:
        """
        Versão assíncrona do process_query.
        Processa a mensagem de um usuário e retorna a resposta do modelo.

        :param query: Texto enviado pelo usuário.
        :return: Texto de resposta gerado pelo modelo.
        """
        input_messages = [HumanMessage(query)]
        output = await self.app.ainvoke({"messages": input_messages}, self.config)
        return output["messages"][-1].content


class ChatBotRag(ChatBotBase):
    """
    Classe para criação de chatbots que utilizam o modelo RAG.
    """

    def initialize(self, use_sqlitesaver: bool) -> None:
        """
        Inicializa o chatbot, selecionando o modelo e definindo se
        as mensagens serão salvas em memória ou em banco de dados.
        """
        self.model = self._get_model(self.think_exp)

        memory_saver = self._get_memory_saver(use_sqlitesaver)

        self.config = {"configurable": {"thread_id": self.thread_id}}
        self.app = RAGSystem(base_path="./RAG Cartões", thread_id=self.config, memory=memory_saver)
        self.app.initialize(reindex=False)

    def process_query(self, query: str) -> str:
        """
        Processa a mensagem de um usuário e retorna a resposta do modelo.

        :param query: Texto enviado pelo usuário.
        :return: Texto de resposta gerado pelo modelo.
        """
        output = self.app.query(query)
        return output["messages"][-1].content

    async def aprocess_query(self, query: str) -> str:
        """
        Versão assíncrona do process_query.
        Processa a mensagem de um usuário e retorna a resposta do modelo.

        :param query: Texto enviado pelo usuário.
        :return: Texto de resposta gerado pelo modelo.
        """
        output = await self.app.aquery(query)
        return output["messages"][-1].content