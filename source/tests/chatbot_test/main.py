import os
import argparse
import requests
from urllib.parse import urljoin
from datetime import timedelta

from dotenv import load_dotenv
from source.tests.chatbot_test.usuario import UsuarioBot

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Script que inicializa UsuarioBot para interagir com o BancoBot API."
    )

    # Flag para ativar os tokens de pensamento
    parser.add_argument(
        "-t",
        "--think",
        action="store_true",
        help="Ativa os tokens de pensamento para o modelo de linguagem.",
    )

    # URL da API do BancoBot
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8080",
        help="URL da API do BancoBot (default: http://localhost:8080).",
    )

    # Prompt personalizado
    parser.add_argument(
        "--prompt",
        type=str,
        help="Prompt personalizado para o UsuarioBot.",
    )

    # Parâmetros de temporização
    parser.add_argument(
        "--typing-speed",
        type=float,
        default=40.0,
        help="Velocidade de digitação em palavras por minuto (default: 40.0).",
    )

    parser.add_argument(
        "--thinking-min",
        type=float,
        default=2.0,
        help="Tempo mínimo de reflexão em segundos (default: 2.0).",
    )

    parser.add_argument(
        "--thinking-max",
        type=float,
        default=10.0,
        help="Tempo máximo de reflexão em segundos (default: 10.0).",
    )

    parser.add_argument(
        "--no-simulate-delays",
        action="store_true",
        help="Desativa os delays simulados (execução rápida).",
    )

    return parser.parse_args()


def main(usuario_prompt: str = None):
    args = parse_args()

    # Verificar se o serviço BancoBot está disponível
    api_url = args.api_url
    try:
        health_url = urljoin(api_url, "/health")
        response = requests.get(health_url, timeout=5)
        response.raise_for_status()
        print(f"Serviço BancoBot disponível em {api_url}.")
    except requests.RequestException as e:
        print(f"ERRO: Serviço BancoBot não está disponível em {api_url}.")
        print(f"Detalhes: {e}")
        print("Por favor, inicie o serviço BancoBot antes de executar este script.")
        return

    # Se um prompt foi fornecido como argumento, use-o em vez do parâmetro usuario_prompt
    prompt_to_use = args.prompt or usuario_prompt

    # Criar UsuarioBot com os parâmetros de temporização
    usuario_bot = UsuarioBot(
        think_exp=args.think,
        persona_id="persona_cli",
        system_message=prompt_to_use,
        api_url=api_url,
        typing_speed_wpm=args.typing_speed,
        thinking_time_range=(args.thinking_min, args.thinking_max),
        simulate_delays=not args.no_simulate_delays,
        temporal_offset=timedelta(0)  # Sem offset quando executado diretamente
    )

    initial_query = "Olá cliente X! Como posso lhe ajudar?"
    usuario_bot.run(initial_query, max_iterations=10)


if __name__ == "__main__":
    main()