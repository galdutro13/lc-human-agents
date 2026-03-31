# Start Usuarios Script

## Schema 3.0
O runtime do `start_usuarios.py` aceita apenas arquivos JSON no schema versionado `3.0`.

Para migrar os arquivos legados do repositÃ³rio:

```bash
python tools/enxame_usuario/migrate_personas_v1_to_v3.py personas_tf.json personas.json personas_carlos.json --output-dir data/migrated
```

Para executar o swarm com o artefato migrado:

```bash
python tools/enxame_usuario/start_usuarios.py --prompts-file data/migrated/personas_tf/personas_tf.v3.json
```

## Comportamento
- Cada item de `simulacoes` referencia `persona_id`, `config_id` e `politica_id`.
- O loader resolve o prompt, a configuraÃ§Ã£o temporal e os metadados estruturados antes da execuÃ§Ã£o.
- O runner propaga `sim_id`, `persona_id`, `config_id`, `politica_id`, `source_slug` e `versao_schema` para rastreabilidade.
- Arquivos legados permanecem apenas como entrada do migrador e artefato de auditoria/rollback.

## Uso

```bash
python tools/enxame_usuario/start_usuarios.py \
  --prompts-file data/migrated/personas_tf/personas_tf.v3.json \
  --window-size 6 \
  --passes 10
```

## Artefatos gerados pelo migrador
- `*.v3.json`: documento canÃ´nico no schema 3.0
- `migration_manifest.json`: resumo de contagens, defaults e pendÃªncias humanas
- `id_map.json`: mapeamento entre IDs legados e IDs resolvidos
- `validation_report.json`: resultado das validaÃ§Ãµes estruturais e semÃ¢nticas
- `semantic_diff_report.json`: comparaÃ§Ã£o entre legado e migrado
