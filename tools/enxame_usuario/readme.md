# Start Usuarios Script

## Descrição
Ferramenta para iniciar múltiplas instâncias de `UsuarioBot` contra o serviço BancoBot API usando exclusivamente o schema `v4.2`.

O arquivo `config_v4_2.json` contém:
- personas e missões desacopladas
- calendário sintético de 90 dias
- pesos determinísticos para `dia_relativo` e `persona_id`
- amostragem controlada para `offset`, `ritmo` e `missao_id`

O script gera `n` simulações, monta o prompt final a partir de `persona + missão` e deriva o deslocamento temporal a partir de `dia_relativo + offset`.

Para inspeção sem executar bots, use:

```bash
python tools/enxame_usuario/export_simulation_preview.py --config-file config_v4_2.json
python tools/enxame_usuario/export_simulation_audit.py --config-file config_v4_2.json
```

## Uso básico

```bash
python tools/bancobot_service/start_banco_service.py
python tools/enxame_usuario/start_usuarios.py --prompts-file config_v4_2.json
```

## Opções principais

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--prompts-file` | Arquivo JSON de entrada em schema v4.2 | obrigatório |
| `--api-url` | URL base da API do BancoBot | `http://localhost:8080` |
| `--sequencial` | Executa as personas uma a uma | `False` |
| `--window-size`, `-w` | Máximo de execuções simultâneas | `4` |
| `--passes`, `-p` | Número de varreduras completas sobre a lista gerada | `1` |
| `--use-thinking`, `-t` | Usa modelo de raciocínio | `False` |
| `--break-probability` | Probabilidade de pausa após mensagem | `0.05` |
| `--break-min` | Pausa mínima em segundos | `60.0` |
| `--break-max` | Pausa máxima em segundos | `3600.0` |
| `--no-simulate-delays` | Desliga atrasos simulados | `False` |

## Resolução de problemas

### Falha ao ler o arquivo de prompts
- Verifique se o JSON é válido.
- Confirme se `versao` é `"4.2"`.
- Valide se `config_v4_2.json` contém `personas`, `missoes`, `janela_temporal` e `amostragem`.

### Falha na conexão com o serviço BancoBot
- Verifique se o serviço responde em `http://localhost:8080/health`.
- Confirme a `--api-url`.

### Problemas de desempenho
- Reduza `--window-size`.
- Use `--sequencial` para depuração.
- Use `--no-simulate-delays` em execuções rápidas.
