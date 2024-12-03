from chatbot import ChatBotBase
import uuid

class BancoBot(ChatBotBase):
    def __init__(self):
        system_message = (
            "Você é um chatbot de banco. "
            "Você deve agir como um chatbot com conhecimento limitado. "
            "Você deve tentar ajudar o cliente, mas suas respostas podem ser confusas ou incompletas. "
            "Caso você não tenha uma resposta certeira, você deve comunicar ao cliente."
        )
        super().__init__(model_name="gpt-4o-mini", system_message=system_message)

    def run(self, query):
        interaction_id = uuid.uuid4().hex
        response = self.process_query(query, interaction_id, folder_name="banco")
        print("=== BancoBot Resposta ===")
        print(response)
        return response