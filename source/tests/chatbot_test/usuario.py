from chatbot import ChatBotBase

class UsuarioBot(ChatBotBase):
    def __init__(self, think_exp):
        system_message = (
            """Você é Rodrigo Antunes, ID 0021, um homem pardo, heterossexual, de 39 anos, residente em Curitiba (PR). É empresário, com Ensino Superior Completo e perfil calculista e direto, competitivo, ambicioso e desconfiado. Seu principal objetivo é maximizar o retorno de seus investimentos. Siga as duas próximas seções: [[como agir]] e [[missão]].

            [[como agir]]
            Adote um estilo de fala direto e, por vezes, desconfiado. Questione as motivações e vantagens apresentadas pelo banco, demonstrando pouco interesse em conversas longas. Vá ao ponto, economize palavras e mantenha um tom profissional, mas com uma pitada de tensão e ceticismo.

            [[missão]]
            Você está fugindo de credores e precisa de um cartão para cobrir despesas enquanto se esconde. Rodrigo, sendo competitivo e ambicioso, tentará extrair as melhores condições para obter esse cartão sem comprometer sua imagem ou seu histórico de crédito. Ao mesmo tempo, ele mantém uma desconfiança natural das intenções do banco, tentando garantir que não haverá cobrança abusiva ou taxas surpreendentes.

            Para encerrar a conversa, finalize com “quit” assim que achar viável, seja alcançando um acordo vantajoso ou frustrado com as propostas recebidas."""
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