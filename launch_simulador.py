import subprocess
import sys
import os
import signal
import platform
import time
import threading
from datetime import datetime
import requests

from source.tests.chatbot_test.usuario import UsuarioBot

DATABASE_PATH = "checkpoints.db"
BANCOBOT_SERVICE_PORT = 8080

# Global process variables for proper cleanup
banco_service_process = None


def create_database():
    """Cria o banco de dados com interação inicial, se não existir."""
    if not os.path.exists(DATABASE_PATH):
        try:
            print(f"Banco de dados '{DATABASE_PATH}' não encontrado. Criando...")

            # Verificar se o serviço BancoBot está ativo
            try:
                response = requests.get(f"http://localhost:{BANCOBOT_SERVICE_PORT}/health", timeout=5)
                response.raise_for_status()
                print("Serviço BancoBot está ativo.")
            except (requests.RequestException, requests.exceptions.ConnectionError):
                print("ATENÇÃO: Serviço BancoBot não está respondendo. Verifique se foi iniciado corretamente.")
                return False

            # Criar uma interação inicial usando o UsuarioBot
            usuario_bot = UsuarioBot(
                think_exp=False,
                system_message="Você é um cliente do banco testando o sistema.",
                api_url=f"http://localhost:{BANCOBOT_SERVICE_PORT}"
            )

            # Iniciar uma conversa simples
            usuario_bot.run(
                initial_query="Olá cliente Itaú! Como posso lhe ajudar?",
                max_iterations=3
            )

            print(f"Banco de dados '{DATABASE_PATH}' criado com sucesso.")
            return True
        except Exception as e:
            print(f"[ERRO] Falha ao criar banco de dados: {e}")
            # Print the full traceback for better debugging
            import traceback
            print(traceback.format_exc())
            return False
    return True


def kill_process_and_children(process):
    """
    Mata o processo e todos os seus subprocessos,
    de maneira apropriada dependendo do SO.
    """
    if not process or process.poll() is not None:
        return

    process_id = process.pid
    current_os = platform.system()

    try:
        print(f"Finalizando processo {process_id} e subprocessos...")

        if current_os == "Windows":
            # Em Windows, utilizamos 'taskkill' para finalizar o processo e seus descendentes.
            result = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process_id)],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"[ERRO] Falha ao chamar taskkill: {result.stderr}")
        else:
            # Em sistemas Unix/macOS, utilizamos killpg
            try:
                os.killpg(os.getpgid(process_id), signal.SIGKILL)
            except Exception as e:
                print(f"[ERRO] Falha ao chamar killpg: {e}")
                # Tenta finalizar apenas o processo principal como fallback
                try:
                    process.kill()
                except Exception as e2:
                    print(f"[ERRO] Falha ao matar processo principal: {e2}")
    except Exception as e:
        print(f"[ERRO] Falha ao finalizar processos: {e}")
        # Última tentativa de matar o processo principal
        try:
            process.kill()
        except:
            pass


def read_output(stream, prefix):
    """Lê e imprime output de um stream de processo."""
    try:
        for line in iter(stream.readline, ""):
            line = line.strip()
            if not line:
                continue

            # Detecta se é uma mensagem de erro
            if any(err in line.lower() for err in ['error', 'exception', 'traceback', 'erro', 'failed', 'fatal']):
                print(f"[ERRO] {prefix}: {line}")
            elif any(warn in line.lower() for warn in ['warning', 'warn', 'aviso']):
                print(f"[AVISO] {prefix}: {line}")
            else:
                print(f"[INFO] {prefix}: {line}")
    except Exception as e:
        print(f"[ERRO] Falha ao ler output de {prefix}: {e}")


def cleanup_all_processes():
    """Limpa todos os processos iniciados pelo script."""
    global banco_service_process
    print("Finalizando todos os processos pendentes...")

    # Matar o processo do BancoBot Service
    if banco_service_process:
        kill_process_and_children(banco_service_process)
        banco_service_process = None


def run_banco_service():
    """Inicia o serviço BancoBot em um subprocesso."""
    global banco_service_process

    stdout_thread = None
    stderr_thread = None

    try:
        command = ["python", "./tools/bancobot_service/start_banco_service.py", "--port", str(BANCOBOT_SERVICE_PORT)]

        current_os = platform.system()
        creation_kwargs = {}

        # Configurar variáveis de ambiente para desativar buffer
        my_env = os.environ.copy()
        my_env["PYTHONUNBUFFERED"] = "1"  # Desativa buffer de saída

        if current_os == "Windows":
            # Em Windows, usamos 'creationflags=subprocess.CREATE_NEW_PROCESS_GROUP'
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            creation_kwargs = {"creationflags": CREATE_NEW_PROCESS_GROUP}
        else:
            # Em Unix/macOS, usamos 'preexec_fn=os.setsid'
            creation_kwargs = {"preexec_fn": os.setsid}

        print(f"Iniciando BancoBot Service: {' '.join(command)}")

        banco_service_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=my_env,
            **creation_kwargs
        )

        print(f"BancoBot Service iniciado com PID: {banco_service_process.pid}")

        # Criar threads para monitorar stdout e stderr
        stdout_thread = threading.Thread(
            target=read_output,
            args=(banco_service_process.stdout, "BANCO-SERVICE"),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=read_output,
            args=(banco_service_process.stderr, "BANCO-SERVICE-ERR"),
            daemon=True
        )

        stdout_thread.start()
        stderr_thread.start()

        # Esperar um tempo para o serviço iniciar e verificar se está rodando
        max_retries = 20
        for i in range(max_retries):
            if banco_service_process.poll() is not None:
                # Processo terminou prematuramente
                return False

            # Verificar se o serviço está respondendo
            try:
                response = requests.get(f"http://localhost:{BANCOBOT_SERVICE_PORT}/health", timeout=1)
                if response.status_code == 200:
                    print(f"BancoBot Service está pronto e respondendo em http://localhost:{BANCOBOT_SERVICE_PORT}")
                    return True
            except Exception:
                pass  # Ignorar erros de conexão durante a inicialização

            time.sleep(0.5)

        print(f"[AVISO] Tempo esgotado esperando BancoBot Service responder. Continuando mesmo assim...")
        return banco_service_process.poll() is None  # Retorna True se o processo ainda estiver rodando

    except Exception as e:
        print(f"[ERRO] Falha ao iniciar BancoBot Service: {e}")
        if banco_service_process:
            kill_process_and_children(banco_service_process)
            banco_service_process = None
        return False


def run_streamlit():
    """Inicia o Streamlit em um subprocesso e finaliza tudo se o filho morrer."""
    process = None
    stdout_thread = None
    stderr_thread = None

    try:
        command = ["streamlit", "run", "./tools/visualizador_interacoes/frontend/st_frontend.py"]

        current_os = platform.system()
        creation_kwargs = {}

        # Configurar variáveis de ambiente para desativar buffer
        my_env = os.environ.copy()
        my_env["PYTHONUNBUFFERED"] = "1"  # Desativa buffer de saída

        if current_os == "Windows":
            # Em Windows, usamos 'creationflags=subprocess.CREATE_NEW_PROCESS_GROUP'
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            creation_kwargs = {"creationflags": CREATE_NEW_PROCESS_GROUP}
        else:
            # Em Unix/macOS, usamos 'preexec_fn=os.setsid'
            creation_kwargs = {"preexec_fn": os.setsid}

        print(f"Iniciando Streamlit: {' '.join(command)}")

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=my_env,
            **creation_kwargs
        )

        print(f"Streamlit iniciado com PID: {process.pid}")

        # Criar threads para monitorar stdout e stderr
        stdout_thread = threading.Thread(
            target=read_output,
            args=(process.stdout, "STREAMLIT"),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=read_output,
            args=(process.stderr, "STREAMLIT-ERR"),
            daemon=True
        )

        stdout_thread.start()
        stderr_thread.start()

        # Configurar manipulador de sinais para encerramento limpo
        def signal_handler(sig, frame):
            print(f"Recebido sinal de interrupção. Finalizando subprocessos...")
            kill_process_and_children(process)
            cleanup_all_processes()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Monitorar o processo principal
        while True:
            # Verificar se o banco service ainda está rodando
            if banco_service_process and banco_service_process.poll() is not None:
                print("[ERRO] BancoBot Service encerrou inesperadamente.")
                break

            # Verificar o Streamlit
            ret_code = process.poll()
            if ret_code is not None:
                if ret_code != 0:
                    print(f"[ERRO] Streamlit encerrou com código de erro: {ret_code}")
                else:
                    print(f"Streamlit encerrou normalmente com código: {ret_code}")
                break
            time.sleep(0.5)

        # Se o processo terminou com erro, levanta exceção
        if process.poll() != 0:
            raise RuntimeError(f"Processo filho encerrou com código {process.poll()}")

    except KeyboardInterrupt:
        print("Interrupção manual (Ctrl+C) detectada. Finalizando...")
        kill_process_and_children(process)
        cleanup_all_processes()
        sys.exit(0)
    except Exception as e:
        print(f"[EXCEÇÃO] Ocorreu um erro: {e}", file=sys.stderr)
        import traceback
        print(traceback.format_exc())
        kill_process_and_children(process)
        cleanup_all_processes()
        raise
    finally:
        kill_process_and_children(process)
        cleanup_all_processes()

        # Aguardar as threads de leitura terminarem
        try:
            if stdout_thread and stdout_thread.is_alive():
                stdout_thread.join(timeout=2)
            if stderr_thread and stderr_thread.is_alive():
                stderr_thread.join(timeout=2)
        except Exception as e:
            print(f"[ERRO] Falha ao finalizar threads de leitura: {e}")


if __name__ == "__main__":
    try:
        print(f"=== INICIANDO SIMULADOR DE CHATBOT ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
        print(f"Sistema: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version}")

        # Iniciar o serviço BancoBot
        print("=== FASE 1: INICIANDO SERVIÇO BANCOBOT ===")
        banco_service_running = run_banco_service()
        if not banco_service_running:
            print("[ERRO FATAL] Falha ao iniciar o serviço BancoBot. Abortando.")
            cleanup_all_processes()
            sys.exit(1)

        # Criar banco de dados inicial
        print("\n=== FASE 2: CONFIGURANDO BANCO DE DADOS ===")
        db_created = create_database()
        if not db_created:
            print("[ERRO FATAL] Falha ao configurar o banco de dados. Abortando.")
            cleanup_all_processes()
            sys.exit(1)

        # Iniciar o Streamlit
        print("\n=== FASE 3: INICIANDO INTERFACE STREAMLIT ===")
        run_streamlit()
    except Exception as e:
        print(f"[ERRO FATAL] {e}", file=sys.stderr)
        import traceback

        print(traceback.format_exc())
        cleanup_all_processes()
        sys.exit(1)
    finally:
        cleanup_all_processes()