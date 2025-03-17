import os
import argparse

from dotenv import load_dotenv
from source.tests.chatbot_test.banco import BancoBot
from source.tests.chatbot_test.usuario import UsuarioBot

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def parse_args():
    parser = argparse.ArgumentParser(
        description="Script principal que inicializa BancoBot e UsuarioBot."
    )

    # Adicionando a flag --think (ou -t)
    parser.add_argument(
        "-t",
        "--think",
        action="store_true",
        help="Ativa os tokens de pensamento para o modelo de linguagem.",
    )

    return parser.parse_args()


def main(usuario_prompt: str = None):
    args = parse_args()

    # Se a flag --think ou -t foi passada, args.think será True
    banco_bot = BancoBot(think_exp=args.think)
    if usuario_prompt:
        usuario_bot = UsuarioBot(think_exp=args.think, system_message=usuario_prompt)
    else:
        usuario_bot = UsuarioBot(think_exp=args.think)

    initial_query = "Olá cliente Itaú! Como posso lhe ajudar?"
    usuario_bot.run(initial_query, banco_bot)


if __name__ == "__main__":
    main()
