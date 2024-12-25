# server_usuario.py
from flask import Flask, request, jsonify
from source.tests.chatbotserver_test.usuario import UsuarioBot

app = Flask(__name__)

usuario_bot = UsuarioBot()

@app.route("/usuario/process", methods=["POST"])
def process():
    data = request.get_json(force=True)
    query = data.get("query", "")
    response = usuario_bot.process_query(query)
    print("=== UsuarioBot Mensagem ===")
    print(response)
    return jsonify({"response": response})

if __name__ == "__main__":
    # Runs on port 5001 by default
    app.run(port=5001)
