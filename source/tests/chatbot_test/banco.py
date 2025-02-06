from source.tests.chatbot_test.chatbot import ChatBotBase

class BancoBot(ChatBotBase):
    def __init__(self, think_exp):
        system_message = (
            "Você é um chatbot de banco. "
            "Você deve agir como um chatbot com conhecimento limitado. "
            "Você deve tentar ajudar o cliente, mas suas respostas podem ser confusas ou incompletas. "
            "Caso você não tenha uma resposta certeira, você deve comunicar ao cliente."
        )
        super().__init__(think_exp=think_exp,
                         system_message=system_message,
                         use_sqlitesaver=False)

    def run(self, query):
        response = self.process_query(query)
        print("=== BancoBot Resposta ===")
        print(response)
        return response