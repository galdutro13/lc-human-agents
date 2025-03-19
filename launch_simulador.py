import subprocess
import sys
import os
import signal
import platform

from source.tests.chatbot_test import test_chatbot

DATABASE_PATH = "checkpoints.db"

def create_database():
    """Cria o banco de dados com interação inicial, se não existir."""
    if not os.path.exists(DATABASE_PATH):
        test_chatbot()

def kill_process_and_children(process: subprocess.Popen) -> None:
    """
    Mata o processo e todos os seus subprocessos,
    de maneira apropriada dependendo do SO.
    """
    if not process:
        return

    # Se o processo ainda não terminou
    if process.poll() is None:
        current_os = platform.system()

        if current_os == "Windows":
            # Em Windows, utilizamos 'taskkill' para finalizar o processo e seus descendentes.
            # /F força a finalização, /T encerra o processo e seus filhos.
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                    text=True
                )
            except Exception as e:
                print(f"[ERRO] Falha ao chamar taskkill: {e}", file=sys.stderr)
        else:
            # Em sistemas Unix/macOS, utilizamos killpg em conjunto com setsid
            # para encerrar o grupo de processos do subprocesso.
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception as e:
                print(f"[ERRO] Falha ao chamar killpg: {e}", file=sys.stderr)

def run_streamlit():
    """Inicia o Streamlit em um subprocesso e finaliza tudo se o filho morrer."""
    process = None

    try:
        command = ["streamlit", "run", "./tools/visualizador_interacoes/frontend/st_frontend.py"]

        current_os = platform.system()

        if current_os == "Windows":
            # Em Windows, usamos 'creationflags=subprocess.CREATE_NEW_PROCESS_GROUP'
            # para criar um novo grupo de processos.
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Em Unix/macOS, usamos 'preexec_fn=os.setsid' para criar um novo grupo de processos.
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid
            )

        # Leitura contínua de stdout
        while True:
            ret = process.poll()
            if ret is not None:
                # Se o processo filho finalizou, matamos o grupo de processos e encerramos.
                print(f"\n[ERRO] O processo filho finalizou com código de saída {ret}.\n", file=sys.stderr)
                kill_process_and_children(process)
                sys.exit(1)

            line = process.stdout.readline()
            if not line:
                # Pode significar que o processo morreu abruptamente ou não há mais linhas.
                break
            print(line, end="")

        # Lê possíveis mensagens de erro do stderr
        for err_line in process.stderr:
            print(err_line, end="", file=sys.stderr)

        # Espera encerramento do processo
        return_code = process.wait()
        if return_code != 0:
            print(f"[ERRO] O processo filho finalizou com código de saída {return_code}.", file=sys.stderr)
            kill_process_and_children(process)
            sys.exit(1)

    except Exception as e:
        print(f"[EXCEÇÃO] Ocorreu um erro: {e}", file=sys.stderr)
        kill_process_and_children(process)
        sys.exit(1)


if __name__ == "__main__":
    create_database()
    run_streamlit()
