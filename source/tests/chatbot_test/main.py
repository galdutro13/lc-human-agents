import argparse
from banco import BancoBot
from usuario import UsuarioBot


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


def main():
    args = parse_args()

    # Se a flag --think ou -t foi passada, args.think será True
    banco_bot = BancoBot(think_exp=args.think)
    usuario_bot = UsuarioBot(think_exp=args.think)

    initial_query = "Olá! Como posso lhe ajudar?"
    usuario_bot.run(initial_query, banco_bot)


if __name__ == "__main__":
    main()
