from banco import BancoBot
from usuario import UsuarioBot

def main():
    banco_bot = BancoBot()
    usuario_bot = UsuarioBot()
    initial_query = "Olá! Como posso lhe ajudar?"
    usuario_bot.run(initial_query, banco_bot)

if __name__ == "__main__":
    main()