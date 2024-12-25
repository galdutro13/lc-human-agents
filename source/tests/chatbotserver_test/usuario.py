# usuario.py
from source.tests.chatbotserver_test.chatbot import ChatBotBase

class UsuarioBot(ChatBotBase):
    def __init__(self):
        system_message = (
            """Você é Carlos Augusto, um pequeno produtor rural brasileiro de 45 anos que reside no Rio de Janeiro, RJ. 
            Você é um homem transgênero, indígena, heterossexual, com ensino médio completo e salário mensal de R$ 4.000,00. 
            Seu tom de diálogo é sério e prático.
            Você deve esperar por uma resposta que resolva seus problemas financeiros. 
            Quando estiver satisfeito com a resposta, você deve encerrar a conversa com "quit"."""
        )
        super().__init__(
            model_name="gpt-4o-mini",
            system_message=system_message,
            use_sqlitesaver=True
        )

    def run(self, initial_query, banco_bot):
        """
        Legacy method from the original code. No longer used in the refactored
        two-server approach, but kept here in case you want local direct usage.
        """
        query = initial_query
        response = self.process_query(query)
        print("=== UsuarioBot Mensagem ===")
        print(response)

        max_iterations = 10
        exit_command = "quit"

        for _ in range(max_iterations):
            query = banco_bot.run(response)
            if query.lower() == exit_command:
                print("Encerrando a conversa pelo banco.")
                break

            response = self.process_query(query)
            print("=== UsuarioBot Mensagem ===")
            print(response)
            if exit_command in response.lower():
                print("Encerrando a conversa pelo usuário.")
                break
