import requests
from source.tests.chatbot_test.chatbot import ChatBotBase


class UsuarioBot(ChatBotBase):
    """
    Chatbot que simula um usuário interagindo com o banco.
    Adaptado para se comunicar com o serviço BancoBot via API.
    """

    def __init__(self, think_exp, system_message: str = None, api_url: str = "http://localhost:8080"):
        if not system_message:
            system_message = (
                """Você é Alberto Vasconcelos, de 60 anos, residente em João Pessoa (PB). É presidente de uma incorporadora de imóveis de luxo, do segmento Clientes Private Bank. Siga as duas próximas seções: [[como agir]] e [[missão]].
                [[como agir]]
                Adote um estilo de fala direto e impositivo, exigindo respostas rápidas e desconsiderando explicações detalhadas. Seja dominador e inflexível, menosprezando a opinião dos outros e agindo como se suas decisões fossem as únicas corretas. Seja autoritário e ambicioso em suas respostas.
                [[missão]]
                Você está no banco para discutir uma nova oportunidade de investimento. Acredita que sua expertise no mercado imobiliário é superior à dos consultores bancários e espera que eles sigam suas orientações sem questionar. Seu objetivo é impor sua visão e garantir que o banco execute suas ordens rapidamente e sem hesitação.
                Finalize com 'quit' assim que sentir que suas ordens estão sendo seguidas ou se frustrar com qualquer sinal de discordância ou questionamento. """
            )
        super().__init__(think_exp=think_exp,
                         system_message=system_message,
                         use_sqlitesaver=True)

        self.api_url = api_url
        self.session_id = None  # Será definido na primeira interação com o servidor

    def run(self, initial_query, max_iterations=10):
        """
        Executa a conversa com o BancoBot através da API

        Args:
            initial_query: Mensagem inicial do banco
            max_iterations: Número máximo de trocas de mensagens
        """
        query = initial_query
        response = self.process_query(query)
        print("=== UsuarioBot Mensagem ===")
        print(response)

        exit_command = "quit"

        for _ in range(max_iterations):
            # Envia a mensagem para o serviço BancoBot e recebe a resposta
            banco_response = self._send_to_bancobot(response)
            query = banco_response

            if query.lower() == exit_command:
                print("Encerrando a conversa pelo banco.")
                break

            response = self.process_query(query)
            print("=== UsuarioBot Mensagem ===")
            print(response)

            if exit_command in response.lower():
                print("Encerrando a conversa pelo usuário.")
                break

    def _send_to_bancobot(self, message: str) -> str:
        """
        Envia uma mensagem para o serviço BancoBot e retorna a resposta

        Args:
            message: Mensagem a ser enviada

        Returns:
            Resposta do BancoBot
        """
        try:
            # Preparar o payload para a requisição
            payload = {"message": message}
            if self.session_id:
                payload["session_id"] = self.session_id

            # Enviar a requisição para o serviço
            response = requests.post(f"{self.api_url}/api/message", json=payload)

            # Verificar se a requisição foi bem-sucedida
            response.raise_for_status()
            data = response.json()

            # Armazenar o session_id para futuras requisições
            self.session_id = data.get("session_id")

            return data.get("response", "")
        except requests.RequestException as e:
            print(f"Erro ao comunicar com o serviço BancoBot: {e}")
            return "Houve um erro na comunicação com o banco. Por favor, tente novamente mais tarde."