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


if __name__ == "__main__":
    try:
        print(f"=== INICIANDO SIMULADOR DE CHATBOT ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
        print(f"Sistema: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version}")
        # Iniciar o Streamlit
        print("\n=== FASE 1: INICIANDO INTERFACE STREAMLIT ===")
        run_streamlit()
    except Exception as e:
        print(f"[ERRO FATAL] {e}", file=sys.stderr)
        import traceback

        print(traceback.format_exc())
        cleanup_all_processes()
        sys.exit(1)
    finally:
        cleanup_all_processes()