# Start Usuarios Script

## Descrição
Ferramenta para iniciar múltiplas instâncias de `UsuarioBot` contra o serviço BancoBot API usando exclusivamente o schema `v4.4`.

O arquivo `config_v4_4.json` contém:
- personas e missões desacopladas
- parâmetros para calendário sintético de 90 dias
- fatores temporais paramétricos para `dia_relativo` e pesos determinísticos para `persona_id`
- amostragem controlada para `offset`, `ritmo` e `missao_id`

O script gera `n` simulações, monta o prompt final a partir de `persona + missão` e deriva o deslocamento temporal a partir de `dia_relativo + offset`.

Para inspeção sem executar bots, use:

```bash
python tools/enxame_usuario/export_simulation_preview.py --config-file config_v4_4.json
python tools/enxame_usuario/export_simulation_audit.py --config-file config_v4_4.json
```

## Uso básico

```bash
python tools/bancobot_service/start_banco_service.py
python tools/enxame_usuario/start_usuarios.py --prompts-file config_v4_4.json
```

## Retomada de execução

Use `--resume` para continuar uma run interrompida sem repetir instâncias que já
foram concluídas ou que já foram iniciadas e ficaram incompletas:

```bash
python tools/enxame_usuario/start_usuarios.py --prompts-file config_v4_4.json --resume
```

A retomada é compatível quando o conteúdo do `--prompts-file` é o mesmo
e o valor de `--passes` também é o mesmo. Outros parâmetros operacionais,
como `--window-size`, `--sequencial`, `--api-url`, `--use-thinking` e
`--no-simulate-delays`, podem mudar entre a execução original e a retomada.

Comportamento esperado:

- Uma execução sem `--resume` cria uma nova run.
- Se já existir uma run incompleta compatível, uma execução sem `--resume`
  falha e orienta continuar com `--resume`.
- Ao retomar, o script executa somente instâncias `pending`, ou seja,
  instâncias que ainda não foram iniciadas.
- Instâncias que estavam `running` em um processo anterior são convertidas para
  `not_finished` antes da retomada. Isso cobre encerramento por `Ctrl+C`, falha
  do processo ou término brusco em que o script não conseguiu registrar a
  conclusão.
- Instâncias `not_finished` são preservadas e não são reexecutadas por
  `--resume`.

O controle de retomada é persistido no mesmo `checkpoints.db` usado pelos
checkpoints do LangGraph. O script cria automaticamente as tabelas auxiliares
`simulation_runs` e `simulation_instances` quando necessário.

Status registrados por instância:

| Status | Significado |
|--------|-------------|
| `pending` | Instância planejada, mas ainda não iniciada |
| `running` | Instância iniciada e com `thread_id` reservado |
| `completed` | Conversa concluída pelo runner |
| `not_finished` | Instância iniciada, mas não concluída |

Cada instância é identificada por `pass_index + simulation_id`, preservando a
fila determinística gerada por `gerar_simulacoes(config)` e por `--passes`.

## Opções principais

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--prompts-file` | Arquivo JSON de entrada em schema v4.4 | obrigatório |
| `--resume` | Retoma a run incompleta compatível mais recente | `False` |
| `--api-url` | URL base da API do BancoBot | `http://localhost:8080` |
| `--sequencial` | Executa as personas uma a uma | `False` |
| `--window-size`, `-w` | Máximo de execuções simultâneas | `4` |
| `--passes`, `-p` | Número de varreduras completas sobre a lista gerada | `1` |
| `--use-thinking`, `-t` | Usa modelo de raciocínio | `False` |
| `--break-probability` | Probabilidade de pausa após mensagem | `0.05` |
| `--break-min` | Pausa mínima em segundos | `60.0` |
| `--break-max` | Pausa máxima em segundos | `3600.0` |
| `--no-simulate-delays` | Desliga atrasos simulados | `False` |

## Exportação e status de conclusão

As rotas JSON do visualizador incluem metadados de execução para runs criadas
após a implementação de `--resume`:

- `GET /interactions/export/all_json_zip`
- `GET /interactions/{thread_id}/json`

Campos adicionados em cada conversa exportada e no `index.json` do ZIP:

| Campo | Descrição |
|-------|-----------|
| `run_id` | Identificador da run persistida em `simulation_runs` |
| `simulation_id` | `id` determinístico da simulação no arquivo v4.4 |
| `pass_index` | Varredura de `--passes` à qual a instância pertence |
| `queue_index` | Posição global da instância na fila planejada |
| `execution_status` | Um dos status da instância, ou `unknown` para conversas antigas |
| `finished` | `true` para `completed`, `false` para `not_finished`, `null` para legado |
| `not_finished` | `true` para instâncias não finalizadas, `null` para legado |

Quando uma instância `not_finished` não chegou a gravar nenhum checkpoint, o ZIP
inclui um JSON placeholder com `messages: []` e os metadados de execução. Assim,
o arquivo exportado ainda permite identificar que aquela instância foi iniciada
e não finalizou.

## Resolução de problemas

### Falha ao ler o arquivo de prompts
- Verifique se o JSON é válido.
- Confirme se `versao` é `"4.4"`.
- Valide se `config_v4_4.json` contém `personas`, `missoes`, `janela_temporal` e `amostragem`.

### Falha na conexão com o serviço BancoBot
- Verifique se o serviço responde em `http://localhost:8080/health`.
- Confirme a `--api-url`.

### Problemas de desempenho
- Reduza `--window-size`.
- Use `--sequencial` para depuração.
- Use `--no-simulate-delays` em execuções rápidas.

### Execução bloqueada por run incompleta
- Use o mesmo `--prompts-file` e o mesmo `--passes` com `--resume`.
- Se a run anterior não deve mais ser considerada, remova ou ajuste
  conscientemente os registros correspondentes em `simulation_runs` e
  `simulation_instances` no `checkpoints.db`.
