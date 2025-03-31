# Start Usuarios Script

## Descrição
Ferramenta para iniciar múltiplas instâncias de UsuarioBot que interagem simultaneamente com o serviço BancoBot API. Permite execução de testes de carga, simulações de concorrência e avaliações de qualidade de atendimento com diferentes perfis de usuário.

## Requisitos
- Python 3.8+
- Requests
- Dotenv
- Threading
- Um serviço BancoBot em execução
- Variável de ambiente `OPENAI_API_KEY` configurada

## Funcionalidades
- Inicialização de múltiplos usuários simulados
- Suporte a execução em paralelo ou sequencial
- Personalização de prompts por usuário
- Verificação automática de disponibilidade do serviço BancoBot
- Gerenciamento de threads com saída ordenada

## Instalação

1. Certifique-se de que o diretório `tools/enxame_usuario/` existe. Se não existir, crie-o:
   ```bash
   mkdir -p tools/enxame_usuario/
   ```

2. Copie o arquivo `start_usuarios.py` para o diretório `tools/enxame_usuario/`:

3. Instale as dependências necessárias:
   ```bash
   pip install requests python-dotenv
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

### Iniciando usuários simulados

Para iniciar um único usuário com configuração padrão:
```bash
python tools/enxame_usuario/start_usuarios.py
```

Para iniciar múltiplos usuários em paralelo:
```bash
python tools/enxame_usuario/start_usuarios.py --num-usuarios 5
```

Para iniciar múltiplos usuários sequencialmente:
```bash
python tools/enxame_usuario/start_usuarios.py --num-usuarios 3 --sequencial
```

Para conectar a um serviço BancoBot em outro endereço:
```bash
python tools/enxame_usuario/start_usuarios.py --api-url http://192.168.1.100:8088
```

### Personalização de Prompts

Você pode fornecer prompts personalizados para cada usuário usando um arquivo JSON:

1. Crie um arquivo JSON com a seguinte estrutura (o número da chave corresponde ao ID do usuário):
   ```json
   {
     "1": "Texto do prompt para o usuário 1...",
     "2": "Texto do prompt para o usuário 2...",
     "3": "Texto do prompt para o usuário 3..."
   }
   ```

2. Execute o script com o parâmetro `--prompts-file`:
   ```bash
   python tools/enxame_usuario/start_usuarios.py --num-usuarios 3 --prompts-file custom_prompts.json
   ```

### Opções de Linha de Comando

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `-n, --num-usuarios` | Número de usuários a iniciar | 1 |
| `--sequencial` | Executa usuários um após o outro | False |
| `--api-url` | URL da API do BancoBot | http://localhost:8080 |
| `--prompts-file` | Arquivo JSON com prompts personalizados | None |

## Estrutura do Arquivo de Prompts

O arquivo de prompts deve ser um JSON válido onde:
- As chaves são strings numéricas ("1", "2", etc.) representando IDs de usuário
- Os valores são strings contendo prompts completos que definem o comportamento do UsuarioBot

Exemplo:
```json
{
  "1": "Você é Ana Silva, 28 anos... [[como agir]] Seja direta e um pouco ansiosa... [[missão]] Você quer entender as opções de financiamento...",
  "2": "Você é Roberto Pereira, 42 anos... [[como agir]] Seja impaciente e exigente... [[missão]] Você precisa de informações..."
}
```

## Interpretação dos Resultados

O script produz logs detalhados durante a execução:
- Confirmação de disponibilidade do serviço BancoBot
- Mensagem de inicialização para cada usuário
- Transcrição das mensagens trocadas por cada usuário
- Notificação quando cada usuário encerra sua conversa
- Resumo após a conclusão de todos os usuários

## Cenários de Uso

### Teste de Carga
```bash
python tools/enxame_usuario/start_usuarios.py --num-usuarios 20
```

### Teste de Diversidade de Perfis
```bash
python tools/enxame_usuario/start_usuarios.py --num-usuarios 5 --prompts-file perfis_diversos.json
```

### Teste de Comportamento Sequencial
```bash
python tools/enxame_usuario/start_usuarios.py --num-usuarios 3 --sequencial
```

## Resolução de Problemas

### Falha na conexão com o serviço BancoBot
- Verifique se o serviço está rodando (`curl http://localhost:8080/health`)
- Verifique se a URL está correta
- Verifique se há firewall ou regras de rede bloqueando a conexão

### Erros nas conversas
- Examine os logs do UsuarioBot e do serviço BancoBot
- Verifique se os prompts estão formatados corretamente
- Confirme que a API key da OpenAI está configurada e é válida

### Problemas de desempenho
- Ajuste o número de usuários para evitar sobrecarga
- Utilize o modo sequencial para reduzir o consumo de recursos
- Monitore o uso de CPU e memória durante a execução