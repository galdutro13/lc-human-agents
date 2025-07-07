# Touchpoint Classifier

Classifica touchpoints em diálogos de chatbot usando a API da OpenAI.

## Instalação

1. Clone o repositório
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure a chave da API OpenAI:
   - Copie `.env.example` para `.env`
   - Adicione sua chave da API no arquivo `.env`
   ```bash
   cp .env.example .env
   # Edite .env e adicione sua chave
   ```

## Uso

### Para um arquivo JSON individual:
```bash
python touchpoint_classifier.py \
  --dialogue_json conversa.json \
  --touchpoints_ai_json Touchpoint_ai.json \
  --touchpoints_human_json Touchpoint_human.json \
  --output_csv analises.csv
```

### Para múltiplos arquivos JSON em um ZIP:
```bash
python touchpoint_classifier.py \
  --dialogue_json conversas.zip \
  --touchpoints_ai_json Touchpoint_ai.json \
  --touchpoints_human_json Touchpoint_human.json \
  --output_csv analises_todas.csv
```

## Formato de Saída

O CSV gerado contém as seguintes colunas:
- **CASE_ID**: ID da interação (thread_id)
- **EVENT_ID**: Índice da mensagem
- **ACTIVITY**: Touchpoint classificado (formato: "TIPO: SUBTIPO")
- **TIMESTAMP**: Timestamp da mensagem
- **RECURSO**: Fontes de dados RAG utilizadas
- **AGENTE**: Tipo de agente ("ai" ou "human")

## Parâmetros Opcionais

- `--openai_model`: Modelo da OpenAI a usar (padrão: "gpt-4o")
- `--batch_size`: Tamanho do lote para processamento (padrão: 10)
- `--temperature`: Temperatura para geração (padrão: 0.0)
- `--log_level`: Nível de log (padrão: "INFO")
- `--no_retry`: Desabilita retry com modelo menor em caso de falha

## Resolução de Problemas

### Erros de classificação
Se você encontrar erros como "Error tokenizing data", pode ser devido a mensagens com caracteres especiais. O script agora:
- Usa formato JSON ao invés de CSV para evitar problemas de parsing
- Limpa mensagens removendo quebras de linha
- Trunca mensagens muito longas

### Depuração
Para mais detalhes sobre o processamento:
```bash
python touchpoint_classifier.py \
  --dialogue_json conversa.json \
  --touchpoints_ai_json Touchpoint_ai.json \
  --touchpoints_human_json Touchpoint_human.json \
  --output_csv analises.csv \
  --log_level DEBUG
```

### Teste
Execute o script de teste para verificar a formatação:
```bash
python test_touchpoint.py
```