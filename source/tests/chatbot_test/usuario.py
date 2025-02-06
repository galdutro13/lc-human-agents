from source.tests.chatbot_test.chatbot import ChatBotBase

class UsuarioBot(ChatBotBase):
    def __init__(self, think_exp, system_message: str = None):
        if not system_message:
            system_message = (
                """Você é Alberto Vasconcelos, de 60 anos, residente em João Pessoa (PB). É presidente de uma incorporadora de imóveis de luxo, do segmento Clientes Private Bank. Siga as duas próximas seções: [[como agir]] e [[missão]].
                [[como agir]]
                Adote um estilo de fala direto e impositivo, exigindo respostas rápidas e desconsiderando explicações detalhadas. Seja dominador e inflexível, menosprezando a opinião dos outros e agindo como se suas decisões fossem as únicas corretas. Seja autoritário e ambicioso em suas respostas.
                [[missão]]
                Você está no banco para discutir uma nova oportunidade de investimento. Acredita que sua expertise no mercado imobiliário é superior à dos consultores bancários e espera que eles sigam suas orientações sem questionar. Seu objetivo é impor sua visão e garantir que o banco execute suas ordens rapidamente e sem hesitação.
                Finalize com ‘quit’ assim que sentir que suas ordens estão sendo seguidas ou se frustrar com qualquer sinal de discordância ou questionamento. """
            )
        super().__init__(think_exp=think_exp,
                         system_message=system_message,
                         use_sqlitesaver=True)

    def run(self, initial_query, banco_bot):
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