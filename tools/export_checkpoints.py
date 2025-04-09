#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para exportar dados de conversas do banco SQLite para CSV.
Desserializa os checkpoints e extrai informações detalhadas das mensagens.
"""

import os
import sqlite3
import csv
from datetime import datetime
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langchain_core.messages import HumanMessage, AIMessage

# Nome do arquivo de saída
output_file = f'../conversation_export.csv'

# Conecta ao banco de dados
db_path = '../checkpoints.db'
if not os.path.exists(db_path):
    print(f"Erro: Banco de dados '{db_path}' não encontrado!")
    exit(1)

conn = sqlite3.connect(db_path)
print(f"Conectado ao banco de dados: {db_path}")

# Obtém todos os checkpoints, ordenados por thread_id e checkpoint_id
cursor = conn.execute(
    """
    SELECT thread_id, checkpoint_id, parent_checkpoint_id, type, checkpoint 
    FROM checkpoints
    ORDER BY thread_id, checkpoint_id
    """
)
rows = cursor.fetchall()

# Verificar se há dados
if not rows:
    print("Nenhum checkpoint encontrado no banco de dados.")
    conn.close()
    exit(0)

print(f"Encontrados {len(rows)} checkpoints para exportação.")

# Prepara o arquivo CSV
with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
    # Define os campos do CSV
    writer = csv.writer(csvfile)
    writer.writerow([
        'thread_id',
        'checkpoint_id',
        'parent_checkpoint_id',
        'timestamp',
        'message_index',
        'message_type',
        'message_id',
        'content',
        'model_name',
        'total_tokens',
        'prompt_tokens',
        'completion_tokens',
        'finish_reason'
    ])

    # Processa cada checkpoint
    for i, (thread_id, checkpoint_id, parent_id, record_type, checkpoint_data) in enumerate(rows):
        print(f"Processando checkpoint {i + 1}/{len(rows)} (thread_id: {thread_id})...", end="\r")

        try:
            # Desserializa o checkpoint usando JsonPlusSerializer
            conversation = JsonPlusSerializer().loads_typed((record_type, checkpoint_data))

            # Extrai o timestamp
            timestamp = conversation.get('ts', '')

            # Verifica se há mensagens
            if 'channel_values' in conversation and 'messages' in conversation['channel_values']:
                messages = conversation['channel_values']['messages']

                # Se não há mensagens, registra uma linha vazia
                if not messages:
                    writer.writerow([
                        thread_id,
                        checkpoint_id,
                        parent_id or '',
                        timestamp,
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        ''
                    ])
                    continue

                # Processa cada mensagem
                for msg_index, msg in enumerate(messages):
                    # Valores padrão
                    message_type = ''
                    message_id = getattr(msg, 'id', '')
                    content = getattr(msg, 'content', '')
                    model_name = ''
                    total_tokens = ''
                    prompt_tokens = ''
                    completion_tokens = ''
                    finish_reason = ''

                    # Determina o tipo de mensagem e extrai metadados específicos
                    if isinstance(msg, HumanMessage):
                        message_type = 'human'
                    elif isinstance(msg, AIMessage):
                        message_type = 'ai'

                        # Extrai metadados de resposta para mensagens AI
                        if hasattr(msg, 'response_metadata') and msg.response_metadata:
                            metadata = msg.response_metadata

                            # Informações de modelo
                            model_name = metadata.get('model_name', '')
                            finish_reason = metadata.get('finish_reason', '')

                            # Informações de tokens
                            if 'token_usage' in metadata:
                                token_usage = metadata['token_usage']
                                total_tokens = token_usage.get('total_tokens', '')
                                prompt_tokens = token_usage.get('prompt_tokens', '')
                                completion_tokens = token_usage.get('completion_tokens', '')

                    # Escreve a linha no CSV
                    writer.writerow([
                        thread_id,
                        checkpoint_id,
                        parent_id or '',
                        timestamp,
                        msg_index,
                        message_type,
                        message_id,
                        content,
                        model_name,
                        total_tokens,
                        prompt_tokens,
                        completion_tokens,
                        finish_reason
                    ])
            else:
                # Se não encontrou mensagens, escreve uma linha vazia
                writer.writerow([
                    thread_id,
                    checkpoint_id,
                    parent_id or '',
                    timestamp,
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    ''
                ])

        except Exception as e:
            # Em caso de erro, registra o erro
            print(f"\nErro ao processar checkpoint {checkpoint_id}: {str(e)}")
            writer.writerow([
                thread_id,
                checkpoint_id,
                parent_id or '',
                '',
                -1,
                'error',
                '',
                f"Erro: {str(e)}",
                '',
                '',
                '',
                '',
                ''
            ])

# Fecha a conexão
conn.close()

print("\nExportação concluída com sucesso!")
print(f"Dados exportados para: {output_file}")