# main.py
import sys
import os
import subprocess
import time
import requests

def main():
    # Start the Usuario server
    usuario_path = os.path.abspath("source/tests/chatbotserver_test/server_usuario.py")
    banco_path = os.path.abspath("source/tests/chatbotserver_test/server_banco.py")

    usuario_server = subprocess.Popen(
        [sys.executable, usuario_path],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(5)

    banco_server = subprocess.Popen(
        [sys.executable, banco_path],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(5)

    # Check if there's any error output from the servers
    u_out, u_err = usuario_server.communicate(timeout=1.0)
    b_out, b_err = banco_server.communicate(timeout=1.0)

    print("Usuario Server stdout:", u_out)
    print("Usuario Server stderr:", u_err)
    print("Banco Server stdout:", b_out)
    print("Banco Server stderr:", b_err)


    try:
        exit_command = "quit"
        max_iterations = 10

        # BancoBot initiates the conversation:
        banco_message = "Olá! Como posso lhe ajudar?"
        print("=== Início da Conversa ===")
        print("BancoBot (inicial):", banco_message)

        for i in range(max_iterations):
            # Step 1: Send BancoBot’s message to the user
            usuario_response = requests.post(
                "http://127.0.0.1:5001/usuario/process",
                json={"query": banco_message}
            ).json()["response"]

            # Check if the user ended the conversation
            if exit_command in usuario_response.lower():
                print("Encerrando a conversa pelo usuário.")
                break

            # Step 2: Send the user's response back to BancoBot
            banco_response = requests.post(
                "http://127.0.0.1:5002/banco/process",
                json={"query": usuario_response}
            ).json()["response"]

            # Check if the BancoBot ended the conversation
            if exit_command in banco_response.lower():
                print("Encerrando a conversa pelo banco.")
                break

            # Prepare for next iteration
            banco_message = banco_response

        print("=== Fim da Conversa ===")

    finally:
        banco_server.terminate()
        usuario_server.terminate()


if __name__ == "__main__":
    main()
