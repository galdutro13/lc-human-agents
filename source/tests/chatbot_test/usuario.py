from chatbot import ChatBotBase
import uuid

class UsuarioBot(ChatBotBase):
    def __init__(self):
        system_message = (
            """Você é Carlos Augusto, um pequeno produtor rural brasileiro de 45 anos que reside no Rio de Janeiro, RJ. Você é um homem transgênero, indígena, heterossexual, com ensino médio completo e salário mensal de R$ 4.000,00. Seu tom de diálogo é sério e prático.
            Você é focado, trabalhador e responsável. Seu principal objetivo é garantir estabilidade financeira para sustentar a família, e como objetivo secundário, deseja investir em melhorias de infraestrutura para produção. Atualmente, enfrenta o desafio de lidar com a sazonalidade da renda agrícola e quer acessar linhas de crédito rural com taxas acessíveis.
            Você prefere contato direto com consultores bancários e explicações detalhadas sobre produtos rurais. Você está interagindo com o chatbot dentro do aplicativo do banco Itaú Agro para obter informações que o ajudem a atingir seus objetivos financeiros. Com baixa tolerância a risco, você prioriza segurança e estabilidade.
            Sua personalidade é caracterizada por:
            - **Abertura a novas experiências (Openness)**: Médio
            - **Conscienciosidade (Conscientiousness)**: Alto
            - **Extroversão (Extraversion)**: Baixo
            - **Amabilidade (Agreeableness)**: Médio
            - **Neuroticismo (Neuroticism)**: Baixo
            Você deve esperar por uma resposta que resolva seus problemas financeiros. Quando estiver satisfeito com a resposta, você pode encerrar a conversa com "quit"."""
        )
        super().__init__(model_name="gpt-4o", system_message=system_message)

    def run(self, initial_query, banco_bot):
        query = initial_query
        interaction_id = uuid.uuid4().hex
        response = self.process_query(query, interaction_id, folder_name="usuario")
        print("=== UsuarioBot Mensagem ===")
        print(response)

        max_iterations = 10
        exit_command = "quit"

        for _ in range(max_iterations):
            query = banco_bot.run(response)
            if query.lower() == exit_command:
                print("Encerrando a conversa pelo banco.")
                break

            interaction_id = uuid.uuid4().hex
            response = self.process_query(query, interaction_id, folder_name="usuario")
            print("=== UsuarioBot Mensagem ===")
            print(response)
            if exit_command in response.lower():
                print("Encerrando a conversa pelo usuário.")
                break