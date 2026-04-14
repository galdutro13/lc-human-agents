# Start Usuarios Script

## Descrição
Ferramenta para iniciar múltiplas instâncias de `UsuarioBot` contra o serviço BancoBot API. O script aceita tanto o schema legado de prompts (`personas_tf.json`) quanto o novo schema amostrado (`config_v3.json`) e normaliza ambos pela mesma interface.

## Requisitos
- Python 3.11+
- Dependências de `requirements.txt`
- Serviço BancoBot em execução
- `OPENAI_API_KEY` configurada

## Uso básico

Inicie o serviço BancoBot:

```bash
python tools/bancobot_service/start_banco_service.py
```

Depois execute as personas:

```bash
python tools/enxame_usuario/start_usuarios.py --prompts-file personas_tf.json
python tools/enxame_usuario/start_usuarios.py --prompts-file config_v3.json
```

## Opções principais

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--prompts-file` | Arquivo JSON de entrada em schema v1.0 ou v3.0 | obrigatório |
| `--api-url` | URL base da API do BancoBot | `http://localhost:8080` |
| `--sequencial` | Executa as personas uma a uma | `False` |
| `--window-size`, `-w` | Máximo de execuções simultâneas | `4` |
| `--passes`, `-p` | Número de varreduras completas sobre o arquivo | `1` |
| `--use-thinking`, `-t` | Usa modelo de raciocínio | `False` |
| `--typing-speed` | Velocidade padrão de digitação | `40.0` |
| `--thinking-min` | Reflexão mínima em segundos | `2.0` |
| `--thinking-max` | Reflexão máxima em segundos | `10.0` |
| `--break-probability` | Probabilidade de pausa após mensagem | `0.05` |
| `--break-min` | Pausa mínima em segundos | `60.0` |
| `--break-max` | Pausa máxima em segundos | `3600.0` |
| `--no-simulate-delays` | Desliga atrasos simulados | `False` |

## Schemas aceitos em `--prompts-file`

### v1.0 legado

```json
{
  "1": {
    "persona": "Prompt completo da persona...",
    "duração": "media",
    "offset": "horario-comercial",
    "weekend": false
  }
}
```

### v3.0 amostrado

```json
{
  "versao": "3.0",
  "personas": {
    "ana_beatriz_silva": {
      "identidade": "Você é Ana Beatriz Silva...",
      "como_agir": "Adote um estilo de fala...",
      "missao": "Você está interagindo..."
    }
  },
  "template_prompt": "{identidade} Siga as duas próximas seções: [[como agir]] e [[missão]]. [[como agir]] {como_agir} [[missão]] {missao}",
  "amostragem": {
    "n": 300,
    "seed": 44,
    "metodo": "ancestral",
    "dag_ordem": ["persona_id", "duracao", "offset", "weekend"],
    "variaveis": {}
  }
}
```

O loader detecta automaticamente a versão. Para v3.0, o arquivo é validado, as simulações são amostradas e os prompts são montados antes de chegarem ao pipeline atual.

## Gerando o `config_v3.json`

```bash
python -m source.scripts.migrate_personas_v1_to_v3 \
  --input personas_tf.json \
  --output config_v3.json \
  --report-output migration_report.json \
  --n 300 \
  --seed 42
```

## Resolução de problemas

### Falha ao ler o arquivo de prompts
- Verifique se o JSON é válido.
- Para v3.0, valide se `versao` é `"3.0"` e se a DAG/campos obrigatórios estão presentes.
- Para v1.0, verifique se cada entrada contém pelo menos o campo `persona`.

### Falha na conexão com o serviço BancoBot
- Verifique se o serviço responde em `http://localhost:8080/health`.
- Confirme a `--api-url`.

### Problemas de desempenho
- Reduza `--window-size`.
- Use `--sequencial` para depuração.
- Use `--no-simulate-delays` em execuções rápidas.
