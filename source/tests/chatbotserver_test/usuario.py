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
                Finalize com 'quit' assim que sentir que suas ordens estão sendo seguidas ou se frustrar com qualquer sinal de discordância ou questionamento. """
            )
        super().__init__(think_exp=think_exp,
                         system_message=system_message,
                         use_sqlitesaver=True)

    def run(self, initial_query, banco_bot=None):
        """
        Método mantido para compatibilidade com o código existente.
        Na nova arquitetura, este método não é mais utilizado diretamente.

        :param initial_query: Mensagem inicial
        :param banco_bot: Instância de BancoBot (não utilizado na nova arquitetura)
        """
        if banco_bot is not None:
            print("AVISO: O método run() está sendo chamado com uma instância de BancoBot. "
                  "Na nova arquitetura, use os endpoints API em vez disso.")

        query = initial_query
        response = self.process_query(query)
        print("=== UsuarioBot Mensagem ===")
        print(response)

        # Como não temos mais acesso direto ao BancoBot, apenas retornamos a resposta
        return response