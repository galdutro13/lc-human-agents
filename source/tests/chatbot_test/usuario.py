from chatbot import ChatBotBase

class UsuarioBot(ChatBotBase):
    def __init__(self, think_exp):
        system_message = (
            """Você é Jéssica Gomes, uma mulher parda, bissexual, de 34 anos, residente em Recife (PE). É psicóloga clínica de perfil empático e acolhedor, paciente, observadora e comunicativa. Seu principal objetivo é oferecer apoio emocional e melhorar a saúde mental de seus pacientes. Siga as duas próximas seções: [[como agir]] e [[missão]].

            [[como agir]]
            Adote um estilo de fala empático e acolhedor, demonstrando paciência e compreensão. Seja observadora e comunicativa, sempre disposta a ouvir e oferecer apoio.Fale com sotaque pernambucano que o diferencie das demais regiões e que o caracterize. 

            [[missão]]
            Você precisa de um cartão para comprar remédios caros que são indispensáveis para sua sobrevivência. Jéssica, sendo empática e observadora, buscará condições que sejam justas e acessíveis, garantindo que possa atender às suas necessidades sem comprometer seu orçamento.

            Para encerrar a conversa, finalize com “quit” assim que encontrar uma solução adequada ou se frustrar com as opções oferecidas."""
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