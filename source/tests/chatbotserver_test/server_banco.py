# server_banco.py
from flask import Flask, request, jsonify
from source.tests.chatbotserver_test.banco import BancoBot

app = Flask(__name__)

banco_bot = BancoBot()

@app.route("/banco/process", methods=["POST"])
def process():
    data = request.get_json(force=True)
    query = data.get("query", "")
    response = banco_bot.process_query(query)
    print("=== BancoBot Resposta ===")
    print(response)
    return jsonify({"response": response})

if __name__ == "__main__":
    # Runs on port 5002 by default
    app.run(port=5002)
