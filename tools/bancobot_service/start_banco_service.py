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
        print("ERRO: OPENAI_API_KEY não definida. Por favor, configure o arquivo .env")
        exit(1)

    args = parse_args()

    print(f"Iniciando Serviço BancoBot em {args.host}:{args.port}...")
    start_server(host=args.host, port=args.port)