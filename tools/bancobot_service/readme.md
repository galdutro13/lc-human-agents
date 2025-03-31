# BancoBot Service

## Descrição
Serviço de API para o BancoBot, implementando uma arquitetura de microserviços que permite a comunicação de múltiplos clientes (UsuarioBots) com o serviço do banco através de uma API RESTful.

## Requisitos
- Python 3.8+
- FastAPI
- Uvicorn
- Dependências do projeto base (`source/tests/chatbot_test/banco.py`)
- Variável de ambiente `OPENAI_API_KEY` configurada

## Estrutura da API

### Endpoints
- `POST /api/message`: Processa mensagens de usuários
  - Aceita: `{"message": "texto da mensagem", "session_id": "id opcional"}`
  - Retorna: `{"response": "resposta do bot", "session_id": "id da sessão"}`

- `GET /api/sessions`: Lista todas as sessões ativas
  - Retorna: `{"sessions": ["id1", "id2", ...], "count": n}`

- `DELETE /api/sessions/{session_id}`: Remove uma sessão específica
  - Retorna: `{"status": "success", "message": "Sessão {id} removida"}`

- `GET /health`: Verifica o status do serviço
  - Retorna: `{"status": "ok", "service": "BancoBot API"}`

### Gerenciamento de Sessões
- Cada interação de usuário é tratada como uma sessão única
- Sessões são identificadas por um ID gerado automaticamente ou fornecido pelo cliente
- Cada sessão mantém seu próprio estado e histórico de conversação
- O serviço mantém as instâncias ativas até que sejam explicitamente encerradas

## Instalação

1. Certifique-se de que o diretório `tools/bancobot_service/` existe. Se não existir, crie-o:
   ```bash
   mkdir -p tools/bancobot_service/
   ```

2. Copie os arquivos `banco_service.py` e `start_banco_service.py` para o diretório `tools/bancobot_service/`:

3. Instale as dependências necessárias:
   ```bash
   pip install fastapi uvicorn python-dotenv
   ```

4. Configure a variável de ambiente OPENAI_API_KEY:
   ```bash
   # No Linux/MacOS
   export OPENAI_API_KEY='sua-chave-api'
   
   # No Windows
   set OPENAI_API_KEY=sua-chave-api
   
   # Ou use um arquivo .env na raiz do projeto
   echo "OPENAI_API_KEY=sua-chave-api" > .env
   ```

## Uso

### Iniciando o Serviço

Para iniciar o serviço com as configurações padrão:
```bash
python tools/bancobot_service/start_banco_service.py
```

Para personalizar o host e a porta:
```bash
python tools/bancobot_service/start_banco_service.py --host 127.0.0.1 --port 8088
```

### Opções de Configuração

- `--host` - Define o endereço IP do servidor (padrão: 0.0.0.0)
- `--port` - Define a porta do servidor (padrão: 8080)

### Monitoramento e Gerenciamento

Para verificar o status do serviço:
```bash
curl http://localhost:8080/health
```

Para listar todas as sessões ativas:
```bash
curl http://localhost:8080/api/sessions
```

Para remover uma sessão específica:
```bash
curl -X DELETE http://localhost:8080/api/sessions/{session_id}
```

## Exemplos de Integração

### Python com Requests
```python
import requests

# Enviar mensagem (nova sessão)
response = requests.post("http://localhost:8080/api/message", 
                       json={"message": "Olá, quero informações sobre cartões de crédito"})
data = response.json()
session_id = data["session_id"]
print(f"Resposta: {data['response']}")

# Continuar conversa na mesma sessão
response = requests.post("http://localhost:8080/api/message", 
                       json={"message": "Qual o limite disponível?", 
                             "session_id": session_id})
data = response.json()
print(f"Resposta: {data['response']}")
```

## Resolução de Problemas

### O servidor não inicia
- Verifique se todas as dependências estão instaladas
- Verifique se a variável OPENAI_API_KEY está configurada
- Verifique se a porta não está sendo usada por outro aplicativo

### Erros nas respostas da API
- Verifique os logs do servidor para mensagens de erro
- Confirme se o formato das requisições está correto
- Verifique se as instâncias do BancoBot estão sendo criadas corretamente

### Consumo excessivo de memória
- Monitore o número de sessões ativas
- Remova sessões inativas regularmente usando o endpoint DELETE