# Start Usuarios

## Descrição

`start_usuarios.py` executa múltiplas instâncias de `UsuarioBot` contra o serviço BancoBot. O runner aceita arquivos de personas em dois formatos:

- `v3.0` (recomendado): schema deduplicado com `metodologia`, `distribuicao_base`, `template_prompt` e `personas`.
- `v1` (legado): dicionário plano já expandido com `persona`, `duração`, `offset` e `weekend`.

Durante o período de transição, o runner detecta automaticamente o schema e sempre converte o input para o mesmo contrato em memória consumido pelo restante do pipeline.

## Requisitos

- Python 3.8+
- `requests`
- `python-dotenv`
- serviço BancoBot disponível
- variável de ambiente `OPENAI_API_KEY`

## Uso

### Execução básica

```bash
python tools/enxame_usuario/start_usuarios.py --prompts-file ./personas_v3.json
```

### Execução paralela com janela fixa

```bash
python tools/enxame_usuario/start_usuarios.py --prompts-file ./personas_v3.json --window-size 6 --passes 2
```

### Execução sequencial

```bash
python tools/enxame_usuario/start_usuarios.py --prompts-file ./personas_v3.json --sequencial
```

### Endpoint alternativo do BancoBot

```bash
python tools/enxame_usuario/start_usuarios.py --prompts-file ./personas_v3.json --api-url http://192.168.1.100:8088
```

## Opções de linha de comando

| Opção | Descrição | Padrão |
|---|---|---|
| `--prompts-file` | Caminho do arquivo JSON de personas | obrigatório |
| `--api-url` | URL base da API do BancoBot | `http://localhost:8080` |
| `--sequencial` | Executa uma persona por vez | `False` |
| `--window-size`, `-w` | Número máximo de personas simultâneas | `4` |
| `--passes`, `-p` | Quantas vezes repetir toda a fila carregada | `1` |
| `--use-thinking`, `-t` | Ativa modelo com tokens de raciocínio | `False` |
| `--typing-speed` | Velocidade padrão de digitação quando o schema não define duração | `40.0` |
| `--thinking-min` | Tempo mínimo de reflexão padrão | `2.0` |
| `--thinking-max` | Tempo máximo de reflexão padrão | `10.0` |
| `--break-probability` | Probabilidade de pausa entre mensagens | `0.05` |
| `--break-min` | Pausa mínima em segundos | `60.0` |
| `--break-max` | Pausa máxima em segundos | `3600.0` |
| `--no-simulate-delays` | Remove esperas reais na execução | `False` |

## Schema v3.0

O arquivo `personas_v3.json` contém:

- `versao`: deve ser `"3.0"`
- `metodologia`: seed, tamanho da amostra, piso mínimo por persona e método de amostragem
- `distribuicao_base`: pesos globais de `duracao`, `offset` e `weekend`
- `template_prompt`: template com `{identidade}`, `{como_agir}` e `{missao}`
- `personas`: fragmentos de prompt, peso relativo da persona e ajustes multiplicativos

O loader:

- valida o schema com Pydantic
- renormaliza distribuições ajustadas por persona
- calcula a quantidade de simulações por persona
- expande o schema para o formato v1-like em memória
- gera IDs sequenciais a partir de `1`

## Compatibilidade com v1

Arquivos legados sem `versao` continuam aceitos temporariamente. Quando isso acontece, o runner informa `Schema detectado: v1` e segue em modo de compatibilidade. A leitura direta do v1 não deve mais ser usada como formato de manutenção principal.

## Artefatos da migração

- `personas_v3.json`: dataset canônico no novo schema
- `tools/enxame_usuario/migrate_personas_v1_to_v3.py`: script que gera o v3 a partir do legado
- `tools/enxame_usuario/personas_v3_methodology.md`: relatório com canonização, anomalias legadas e racional dos ajustes

## Troubleshooting

- Se o runner falhar antes da execução, valide se `personas_v3.json` existe e passa no loader.
- Se o log mostrar `Schema detectado: v1`, o arquivo ainda está no formato legado.
- Se o BancoBot não responder, confira `http://localhost:8080/health`.
- Para eliminar tempo de espera real durante testes locais, use `--no-simulate-delays`.
