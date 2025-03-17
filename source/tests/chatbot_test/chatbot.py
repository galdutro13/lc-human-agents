import secrets
import sqlite3
from typing import Union

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from source.chat_graph import ModelName, ClassicChatFunction, ClassicWorkflowBuilder, get_llm
from source.prompt_manager.base import CustomSystemPromptStrategy


class ChatBotBase:
    """
    Classe base para criação de chatbots. Configura o modelo, gera o prompt e
    constrói o fluxo de trabalho para processar interações com o usuário.
    """

    def __init__(
        self,
        think_exp: bool,
        system_message: str,
        use_sqlitesaver: bool = False
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
        self.thread_id = secrets.token_hex(3)

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
            print("Simulação iniciada usando GEMINI_THINKING_EXP")
            return get_llm(ModelName.GEMINI_THINKING_EXP)
        print("Simulação iniciada usando GPT4_MINI")
        return get_llm(ModelName.GPT4_MINI)

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
