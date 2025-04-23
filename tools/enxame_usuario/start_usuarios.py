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


def iniciar_usuario(id_usuario, prompt_personalizado=None, api_url="http://localhost:8080",
                    typing_speed_wpm=40.0, thinking_time_range=(2, 10),
                    break_probability=0.05, break_time_range=(60, 3600),
                    simulate_delays=False):
    """
    Inicia um UsuarioBot com configuração personalizada, incluindo parâmetros de temporização.

    Args:
        id_usuario: Identificador único do usuário
        prompt_personalizado: Prompt personalizado para o usuário (opcional)
        api_url: URL da API do BancoBot
        typing_speed_wpm: Velocidade média de digitação em palavras por minuto
        thinking_time_range: Faixa de tempo para pensar (min, max) em segundos
        break_probability: Probabilidade de fazer uma pausa após enviar uma mensagem
        break_time_range: Faixa de tempo para pausas (min, max) em segundos
        simulate_delays: Se deve aguardar os atrasos simulados
    """
    print(f"Iniciando Usuário {id_usuario}...")

    # Usar o prompt personalizado ou manter o padrão
    usuario_bot = UsuarioBot(
        think_exp=True,
        system_message=prompt_personalizado,
        api_url=api_url,
        typing_speed_wpm=typing_speed_wpm,
        thinking_time_range=thinking_time_range,
        break_probability=break_probability,
        break_time_range=break_time_range,
        simulate_delays=simulate_delays
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

    # Parâmetros de temporização
    parser.add_argument("--typing-speed", type=float, default=40.0,
                        help="Velocidade média de digitação em palavras por minuto (padrão: 40)")
    parser.add_argument("--thinking-min", type=float, default=2.0,
                        help="Tempo mínimo de reflexão em segundos (padrão: 2)")
    parser.add_argument("--thinking-max", type=float, default=10.0,
                        help="Tempo máximo de reflexão em segundos (padrão: 10)")
    parser.add_argument("--break-probability", type=float, default=0.05,
                        help="Probabilidade de fazer uma pausa após enviar uma mensagem (padrão: 0.05)")
    parser.add_argument("--break-min", type=float, default=60.0,
                        help="Tempo mínimo de pausa em segundos (padrão: 60)")
    parser.add_argument("--break-max", type=float, default=3600.0,
                        help="Tempo máximo de pausa em segundos (padrão: 3600)")
    parser.add_argument("--no-simulate-delays", action="store_true",
                        help="Não aguardar pelos atrasos simulados (default: aguarda)")

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
            args=(user_id, user_prompt, args.api_url),
            kwargs={
                "typing_speed_wpm": args.typing_speed,
                "thinking_time_range": (args.thinking_min, args.thinking_max),
                "break_probability": args.break_probability,
                "break_time_range": (args.break_min, args.break_max),
                "simulate_delays": not args.no_simulate_delays
            }
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