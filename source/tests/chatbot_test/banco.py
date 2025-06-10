# source/tests/chatbot_test/banco.py (MODIFIED)
from typing import Optional
from source.tests.chatbot_test.chatbot import ChatBotRag


class BancoBot(ChatBotRag):
    """
    Chatbot que simula um atendente de banco.
    Adaptado para funcionar como um serviço via API com suporte a logging.
    """

    def __init__(self, think_exp: bool, persona_id: Optional[str] = None,
                 thread_id: Optional[str] = None):
        system_message = (
            "Você é um chatbot de banco. "
            "Você deve agir como um chatbot com conhecimento limitado. "
            "Você deve tentar ajudar o cliente, mas suas respostas podem ser confusas ou incompletas. "
            "Caso você não tenha uma resposta certeira, você deve comunicar ao cliente."
        )
        super().__init__(
            think_exp=think_exp,
            system_message=system_message,
            use_sqlitesaver=False,
            thread_id=thread_id,
            persona_id=persona_id,
            enable_rag_logging=True  # Enable RAG logging
        )

    def process_message(self, query):
        """
        Processa uma mensagem e retorna a resposta.
        Método específico para ser usado pela API.

        Args:
            query: Mensagem a ser processada

        Returns:
            Resposta do bot
        """
        response = self.process_query(query)
        print(f"[BancoBot] Processando: '{query[:50]}...' -> '{response[:50]}...'")
        return response

    async def aprocess_message(self, query):
        """
        Processa uma mensagem de forma assíncrona e retorna a resposta.
        Método específico para ser usado pela API em modo assíncrono.

        Args:
            query: Mensagem a ser processada

        Returns:
            Resposta do bot
        """
        response = await self.aprocess_query(query)
        print(f"[BancoBot] Processando assíncrono: '{query[:50]}...' -> '{response[:50]}...'")
        return response

    def run(self, query):
        """
        Método legado mantido para compatibilidade.

        Args:
            query: Mensagem a ser processada

        Returns:
            Resposta do bot
        """
        response = self.process_query(query)
        print("=== BancoBot Resposta ===")
        print(response)
        return response