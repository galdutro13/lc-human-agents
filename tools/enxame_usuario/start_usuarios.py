import os
import time
import argparse
import threading
from dotenv import load_dotenv
import requests
import json
from source.tests.chatbot_test.usuario import UsuarioBot


def load_prompt_from_file(file_path):
    """Carrega um prompt de um arquivo de texto."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Erro ao carregar prompt do arquivo {file_path}: {e}")
        return None


def iniciar_usuario(id_usuario, prompt_personalizado=None, api_url="http://localhost:8080"):
    """
    Inicia um UsuarioBot com configuração personalizada.

    Args:
        id_usuario: Identificador único do usuário
        prompt_personalizado: Prompt personalizado para o usuário (opcional)
        api_url: URL da API do BancoBot
    """
    print(f"Iniciando Usuário {id_usuario}...")

    # Usar o prompt personalizado ou manter o padrão
    usuario_bot = UsuarioBot(
        think_exp=False,
        system_message=prompt_personalizado,
        api_url=api_url
    )

    # Iniciar a conversa
    try:
        usuario_bot.run(
            initial_query="Olá cliente Itaú! Como posso lhe ajudar?",
            max_iterations=10
        )
        print(f"Usuário {id_usuario} encerrou a conversa.")
    except Exception as e:
        print(f"Erro na execução do Usuário {id_usuario}: {e}")


def check_server_availability(api_url):
    """Verifica se o servidor BancoBot está disponível."""
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code == 200:
            return True
        return False
    except requests.RequestException:
        return False


if __name__ == "__main__":
    # Carregar variáveis de ambiente
    load_dotenv()

    # Verificar variáveis de ambiente necessárias
    if not os.getenv("OPENAI_API_KEY"):
        print("ERRO: OPENAI_API_KEY não definida. Configure o arquivo .env")
        exit(1)

    # Configurar o parser de argumentos
    parser = argparse.ArgumentParser(description="Inicia múltiplos usuários simulados para teste")
    parser.add_argument("-n", "--num-usuarios", type=int, default=1, help="Número de usuários a serem iniciados")
    parser.add_argument("--sequencial", action="store_true",
                        help="Executa os usuários sequencialmente (padrão: paralelo)")
    parser.add_argument("--api-url", type=str, default="http://localhost:8080", help="URL da API do BancoBot")
    parser.add_argument("--prompts-file", type=str, help="Arquivo JSON com prompts personalizados para cada usuário")

    args = parser.parse_args()

    # Verificar disponibilidade do servidor
    if not check_server_availability(args.api_url):
        print(f"ERRO: Servidor BancoBot não está disponível em {args.api_url}")
        print("Inicie o servidor antes de executar este script")
        exit(1)

    # Carregar prompts personalizados, se fornecidos
    prompts = {}
    if args.prompts_file:
        try:
            with open(args.prompts_file, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
            print(f"Carregados {len(prompts)} prompts personalizados.")
        except Exception as e:
            print(f"Erro ao carregar prompts do arquivo {args.prompts_file}: {e}")
            exit(1)

    # Criar threads para cada usuário
    threads = []
    for i in range(args.num_usuarios):
        user_id = i + 1
        # Usar prompt personalizado se disponível, ou None para usar o padrão
        user_prompt = prompts.get(str(user_id)) if prompts else None

        thread = threading.Thread(
            target=iniciar_usuario,
            args=(user_id, user_prompt, args.api_url)
        )
        threads.append(thread)

    # Iniciar threads (modo paralelo ou sequencial)
    if args.sequencial:
        # Execução sequencial
        print(f"Iniciando {args.num_usuarios} usuários em modo SEQUENCIAL")
        for thread in threads:
            thread.start()
            thread.join()
    else:
        # Execução em paralelo
        print(f"Iniciando {args.num_usuarios} usuários em modo PARALELO")
        for thread in threads:
            thread.start()
            # Pequeno delay para evitar colisões na API
            time.sleep(0.5)

        # Aguardar todas as threads terminarem
        for thread in threads:
            thread.join()

    print("Todos os usuários concluíram suas conversas.")