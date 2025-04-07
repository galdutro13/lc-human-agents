import os
import argparse
from dotenv import load_dotenv
from banco_service import start_server


def parse_args():
    parser = argparse.ArgumentParser(
        description="Inicia o serviço BancoBot API."
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host para o servidor (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Porta para o servidor (default: 8080)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    # Carregar variáveis de ambiente
    load_dotenv()

    # Verificar se as variáveis necessárias estão definidas
    if not os.getenv("OPENAI_API_KEY"):
        # Tenta definir a chave a partir do ambiente atual caso não esteja no .env
        openai_key = os.environ.get("OPENAI_API_KEY")
        if not openai_key:
            print("ERRO: OPENAI_API_KEY não definida. Por favor, configure o arquivo .env")
            exit(1)
        else:
            # Define a variável para o processo atual
            os.environ["OPENAI_API_KEY"] = openai_key
            print("OPENAI_API_KEY encontrada no ambiente e será utilizada")

    args = parse_args()

    print(f"Iniciando Serviço BancoBot em {args.host}:{args.port}...")
    start_server(host=args.host, port=args.port)