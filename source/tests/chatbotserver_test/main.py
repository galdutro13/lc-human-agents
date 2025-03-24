import os
import sys
import argparse
import asyncio
import httpx
from typing import Optional, Dict, Any
import json

from dotenv import load_dotenv
from api_client import BancoApiClient, UsuarioApiClient

# Carregar variáveis de ambiente
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# URLs dos serviços
BANCO_API_URL = os.getenv("BANCO_API_URL", "http://localhost:8000")
USUARIO_API_URL = os.getenv("USUARIO_API_URL", "http://localhost:8001")

# Clientes API
banco_client = BancoApiClient(BANCO_API_URL)
usuario_client = UsuarioApiClient(USUARIO_API_URL)


def parse_args():
    """Parse argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Script principal que coordena os serviços BancoBot e UsuarioBot."
    )

    # Adicionar a flag --think (ou -t)
    parser.add_argument(
        "-t",
        "--think",
        action="store_true",
        help="Ativa os tokens de pensamento para o modelo de linguagem.",
    )

    # Adicionar o parâmetro de prompt personalizado
    parser.add_argument(
        "-p",
        "--prompt",
        type=str,
        help="Prompt personalizado para o UsuarioBot.",
    )

    # Adicionar o parâmetro de mensagem inicial
    parser.add_argument(
        "-m",
        "--message",
        type=str,
        default="Olá cliente Itaú! Como posso lhe ajudar?",
        help="Mensagem inicial do BancoBot.",
    )

    return parser.parse_args()


async def main(usuario_prompt: Optional[str] = None, initial_message: str = None):
    """
    Função principal que coordena os serviços BancoBot e UsuarioBot.

    :param usuario_prompt: Prompt personalizado para o UsuarioBot
    :param initial_message: Mensagem inicial do BancoBot
    """
    args = parse_args()

    # Definir configurações a partir dos argumentos
    think_exp = args.think
    usuario_prompt = usuario_prompt or args.prompt
    initial_message = initial_message or args.message

    try:
        print("=== Iniciando conversa entre BancoBot e UsuarioBot ===")

        # 1. Criar sessão de UsuarioBot
        config = {
            "think_exp": think_exp,
            "system_message": usuario_prompt
        }

        usuario_session = await usuario_client.create_session(config)
        usuario_thread_id = usuario_session["thread_id"]
        print(f"Sessão UsuarioBot criada: {usuario_thread_id}")

        # 2. Iniciar conversa
        start_result = await usuario_client.request(
            "POST",
            f"/conversation/{usuario_thread_id}/start",
            params={"initial_message": initial_message}
        )

        print(f"\nConversa iniciada:")
        print(f"- UsuarioBot: {usuario_thread_id}")
        print(f"- BancoBot: {start_result['banco_thread_id']}")
        print("\n=== Mensagens iniciais ===")
        print(f"BancoBot: {initial_message}")
        print(f"UsuarioBot: {start_result['initial_response']}")
        print(f"BancoBot: {start_result['banco_response']}")

        print("\nConversa continuando em segundo plano. Pressione Ctrl+C para sair.")

        # 3. Aguardar conclusão da conversa (simulação)
        try:
            while True:
                # Verificar status a cada 2 segundos
                await asyncio.sleep(2)

                # Verificar se a conversa ainda está ativa
                usuario_status = await usuario_client.request(
                    "GET",
                    f"/status/{usuario_thread_id}"
                )

                if not usuario_status["is_active"]:
                    print("\n=== Conversa encerrada ===")
                    break

        except KeyboardInterrupt:
            print("\n=== Conversa interrompida pelo usuário ===")

    except httpx.ConnectError:
        print("ERROR: Could not connect to services. Make sure both BancoBot and UsuarioBot services are running.")
        print(f"- BancoBot should be at: {BANCO_API_URL}")
        print(f"- UsuarioBot should be at: {USUARIO_API_URL}")
        sys.exit(1)

    except httpx.RequestError as e:
        print(f"Erro de conexão: {str(e)}")
        print("Verifique se os serviços BancoBot e UsuarioBot estão em execução.")

    except Exception as e:
        print(f"Erro: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())