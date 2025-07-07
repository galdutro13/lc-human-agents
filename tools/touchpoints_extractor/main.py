#!/usr/bin/env python3
"""Touchpoint Classifier - JSON Version com Eventos de Sistema
==============================================================

Transforma diálogos de chatbot em formato JSON em um conjunto de classificações de *touchpoints*,
utilizando a API da OpenAI para inferir *TIPO* e *SUBTIPO* de cada mensagem de acordo
com catálogos específicos para *bot* e *usuário*.

Adiciona eventos artificiais de início e fim de diálogo marcados como "system".

Suporta arquivos JSON individuais ou arquivos ZIP contendo múltiplos JSONs.

Configuração:
- Crie um arquivo .env na raiz do projeto com: OPENAI_API_KEY=sua_chave_aqui

O script segue boas práticas de engenharia de software:

- **Estrutura modular**: funções puras com responsabilidades bem definidas.
- **Tipagem estática** via ``typing``.
- **Argumentos de linha de comando** com ``argparse``.
- **Logs estruturados** com ``logging``.
- **Controle de erros** explícito.
- **Progress bar** com ``tqdm``.
- **Documentação** num *docstring* inicial e em todas as funções.
- **Conformidade PEP 8/PEP 257** – pronto para ``ruff``/``black``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Dict, List
from io import StringIO

import openai
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm


# --------------------------------------------------------------------------- #
# Configuração                                                                #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Settings:
    """Configurações globais do script."""

    dialogue_json: Path
    touchpoints_ai_json: Path
    touchpoints_human_json: Path
    output_csv: Path
    openai_model: str = "gpt-4.1-2025-04-14"
    temperature: float = 0.0
    log_level: str = "INFO"
    rate_limit_delay: float = 0.5  # Delay entre chamadas para evitar rate limiting

    @staticmethod
    def from_cli() -> "Settings":
        """Constrói :class:`Settings` a partir da linha de comando."""
        parser = argparse.ArgumentParser(
            description=(
                "Classifica touchpoints em diálogos JSON usando a API da OpenAI.\n"
                "Processa MENSAGEM POR MENSAGEM para máxima precisão.\n\n"
                "Exemplo de uso:\n  python touchpoint_classifier.py "
                "--dialogue_json conversa.json "
                "--touchpoints_ai_json Touchpoint_ai.json "
                "--touchpoints_human_json Touchpoint_human.json "
                "--output_csv analisesGeradas.csv\n\n"
                "Ou com ZIP:\n  python touchpoint_classifier.py "
                "--dialogue_json conversas.zip "
                "--touchpoints_ai_json Touchpoint_ai.json "
                "--touchpoints_human_json Touchpoint_human.json "
                "--output_csv analisesGeradas.csv"
            ),
            formatter_class=argparse.RawTextHelpFormatter,
        )
        parser.add_argument("--dialogue_json", type=Path, required=True)
        parser.add_argument("--touchpoints_ai_json", type=Path, required=True)
        parser.add_argument("--touchpoints_human_json", type=Path, required=True)
        parser.add_argument("--output_csv", type=Path, required=True)
        parser.add_argument("--openai_model", default="gpt-4o")
        parser.add_argument("--temperature", type=float, default=0.0)
        parser.add_argument("--log_level", default="INFO")
        parser.add_argument("--rate_limit_delay", type=float, default=0.5,
                          help="Delay em segundos entre chamadas à API (padrão: 0.5)")
        args = parser.parse_args()

        return Settings(
            dialogue_json=args.dialogue_json,
            touchpoints_ai_json=args.touchpoints_ai_json,
            touchpoints_human_json=args.touchpoints_human_json,
            output_csv=args.output_csv,
            openai_model=args.openai_model,
            temperature=args.temperature,
            log_level=args.log_level.upper(),
            rate_limit_delay=args.rate_limit_delay,
        )


# --------------------------------------------------------------------------- #
# Utilidades                                                                  #
# --------------------------------------------------------------------------- #

def configure_logging(level: str = "INFO") -> None:
    """Configura saída de log padrão."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_openai_api_key() -> str:
    """Recupera a chave da API com prioridade para arquivo .env."""
    # Carrega variáveis do arquivo .env se existir
    load_dotenv()
    
    # Tenta obter a chave da API em ordem de prioridade
    api_key = os.getenv("OPENAI_API_KEY")
    
    # Se não encontrar no ambiente, tenta ler de arquivo especificado
    if not api_key:
        api_key_file = os.getenv("OPENAI_API_KEY_FILE")
        if api_key_file and Path(api_key_file).exists():
            api_key = Path(api_key_file).read_text().strip()
    
    if not api_key:
        raise RuntimeError(
            "Chave da OpenAI não encontrada. Defina 'OPENAI_API_KEY' no arquivo .env ou "
            "como variável de ambiente, ou defina 'OPENAI_API_KEY_FILE' apontando para "
            "um arquivo contendo a chave."
        )
    return api_key


def parse_timestamp(timestamp_str: str) -> datetime:
    """Converte string de timestamp para objeto datetime."""
    try:
        # Tenta primeiro com microsegundos
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except:
        try:
            # Tenta sem microsegundos
            return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
        except:
            # Se falhar, retorna datetime atual
            logging.warning(f"Não foi possível parsear timestamp: {timestamp_str}")
            return datetime.now()


def subtract_one_second(timestamp_str: str) -> str:
    """Subtrai um segundo de um timestamp."""
    dt = parse_timestamp(timestamp_str)
    dt_minus_one = dt - timedelta(seconds=1)
    # Retorna no mesmo formato
    return dt_minus_one.isoformat()


# --------------------------------------------------------------------------- #
# Leitura de Diálogos                                                         #
# --------------------------------------------------------------------------- #

def read_dialogue_json(json_path: Path) -> List[Dict]:
    """Lê um arquivo JSON de diálogo e retorna lista de diálogos."""
    with json_path.open(encoding="utf-8") as fp:
        data = json.load(fp)
    # Se for um único diálogo, retorna como lista
    if isinstance(data, dict) and "messages" in data:
        return [data]
    # Se já for uma lista de diálogos
    return data


def read_dialogues_from_zip(zip_path: Path) -> List[Dict]:
    """Lê múltiplos arquivos JSON de um arquivo ZIP."""
    dialogues = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for filename in zf.namelist():
            if filename.endswith('.json'):
                with zf.open(filename) as f:
                    content = f.read().decode('utf-8')
                    data = json.loads(content)
                    if isinstance(data, dict) and "messages" in data:
                        dialogues.append(data)
                    elif isinstance(data, list):
                        dialogues.extend(data)
    return dialogues


def convert_dialogues_to_dataframe(dialogues: List[Dict]) -> pd.DataFrame:
    """Converte lista de diálogos JSON para DataFrame."""
    rows = []
    global_event_id = 0  # Contador global para EVENT_ID
    
    for dialogue in dialogues:
        thread_id = dialogue.get("thread_id", "unknown")
        messages = dialogue.get("messages", [])
        
        # Ordena mensagens por index interno para manter ordem cronológica
        messages = sorted(messages, key=lambda x: x.get("index", 0))
        
        # Adiciona evento START-DIALOGUE-SYTEM (com typo mantido para compatibilidade)
        if messages:
            # Pega o timestamp da primeira mensagem real
            first_timestamp = None
            for msg in messages:
                if msg["type"] == "ai":
                    first_timestamp = msg.get("timing_metadata", {}).get("banco_generation_timestamp")
                else:
                    first_timestamp = msg.get("simulated_timestamp")
                if first_timestamp:
                    break
            
            if first_timestamp:
                # Subtrai 1 segundo para o evento de start
                start_timestamp = subtract_one_second(first_timestamp)
                
                rows.append({
                    "CASE_ID": thread_id,
                    "EVENT_ID": global_event_id,
                    "INTERNAL_INDEX": -1,  # Índice especial para start
                    "Falante": "system",
                    "Mensagem": "",
                    "TIMESTAMP": start_timestamp,
                    "RECURSO": "",
                    "AGENTE": "system",
                    "ACTIVITY": "START-DIALOGUE-SYTEM"  # Mantendo o typo original
                })
                global_event_id += 1
        
        # Processa mensagens reais
        for msg in messages:
            # Determina o timestamp correto
            timestamp = None
            if msg["type"] == "ai":
                timestamp = msg.get("timing_metadata", {}).get("banco_generation_timestamp")
            else:  # human
                timestamp = msg.get("simulated_timestamp")
            
            # Se não encontrar, usa o timestamp geral
            if not timestamp:
                timestamp = msg.get("simulated_timestamp", "")
            
            # Extrai rag_datasources
            rag_sources = msg.get("rag_datasources", [])
            rag_sources_str = ", ".join(rag_sources) if rag_sources else ""
            
            row = {
                "CASE_ID": thread_id,
                "EVENT_ID": global_event_id,
                "INTERNAL_INDEX": msg.get("index", 0),
                "Falante": "Bot" if msg["type"] == "ai" else "Usuário",
                "Mensagem": msg.get("content", ""),
                "TIMESTAMP": timestamp,
                "RECURSO": rag_sources_str,
                "AGENTE": msg["type"],
                "ACTIVITY": None  # Será preenchido depois
            }
            rows.append(row)
            global_event_id += 1
        
        # Adiciona evento END-DIALOGUE-SYSTEM
        if messages:
            # Pega o timestamp da última mensagem real
            last_timestamp = rows[-1]["TIMESTAMP"] if rows else None
            
            if last_timestamp:
                rows.append({
                    "CASE_ID": thread_id,
                    "EVENT_ID": global_event_id,
                    "INTERNAL_INDEX": 999999,  # Índice especial para end
                    "Falante": "system",
                    "Mensagem": "",
                    "TIMESTAMP": last_timestamp,  # Mesmo timestamp da última atividade
                    "RECURSO": "",
                    "AGENTE": "system",
                    "ACTIVITY": "END-DIALOGUE-SYSTEM"
                })
                global_event_id += 1
    
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Funções de Classificação                                                    #
# --------------------------------------------------------------------------- #

def load_touchpoints(path: Path) -> List[str]:
    """Carrega catálogo de touchpoints do formato array."""
    with path.open(encoding="utf-8") as fp:
        data = json.load(fp)
    
    # Extrai apenas os subtipos do array de objetos
    if isinstance(data, list):
        return [item.get("subtipo", "") for item in data if "subtipo" in item]
    
    # Fallback para formato antigo (dicionário)
    if isinstance(data, dict):
        # Concatena todos os subtipos de todos os tipos
        all_subtipos = []
        for subtipos in data.values():
            if isinstance(subtipos, list):
                all_subtipos.extend(subtipos)
        return all_subtipos
    
    return []


def build_prompt(
    message: pd.Series, touchpoints: List[str], actor: str
) -> str:
    """Monta prompt de classificação para UMA ÚNICA mensagem."""
    # Lista os touchpoints disponíveis em maiúsculas
    tp_list = "\n".join(f"- {tp.upper()}" for tp in touchpoints)
    
    return f"""\
Analise a seguinte mensagem de um {actor.lower()} em um chatbot bancário e identifique
o TOUCHPOINT correspondente usando EXCLUSIVAMENTE os touchpoints listados abaixo.

MENSAGEM:
{actor}: {message['Mensagem']}

TOUCHPOINTS DISPONÍVEIS:
{tp_list}

INSTRUÇÕES:
- Escolha APENAS UM touchpoint da lista acima que melhor descreve a mensagem
- Se nenhum touchpoint se aplicar perfeitamente, escolha o mais próximo
- Use SEMPRE letras maiúsculas
- Retorne APENAS o nome do touchpoint, sem explicações adicionais

TOUCHPOINT:"""


def classify_message(
    message: pd.Series,
    touchpoints: List[str],
    actor: str,
    settings: Settings,
) -> str:
    """Classifica UMA ÚNICA mensagem usando a API."""
    prompt = build_prompt(message, touchpoints, actor)
    
    try:
        response = openai.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.temperature,
            max_tokens=100  # Resposta curta esperada
        )
        
        # Extrai apenas o touchpoint da resposta
        touchpoint = response.choices[0].message.content.strip()
        
        # Remove possíveis aspas ou caracteres extras
        touchpoint = touchpoint.replace('"', '').replace("'", '').strip()
        
        # Valida se o touchpoint está na lista (case insensitive)
        touchpoints_upper = [tp.upper() for tp in touchpoints]
        if touchpoint.upper() not in touchpoints_upper:
            logging.warning(f"Touchpoint não reconhecido: {touchpoint}")
            # Tenta encontrar o mais próximo ou retorna vazio
            return ""
            
        return touchpoint.upper()
        
    except Exception as e:
        logging.error(f"Erro ao classificar mensagem: {e}")
        return ""


def process_actor(
    df: pd.DataFrame, actor: str, touchpoints: List[str], settings: Settings
) -> pd.DataFrame:
    """Processa todas as mensagens de um ator, uma por vez."""
    df_subset = df[df["Falante"] == actor].copy()
    if len(df_subset) == 0:
        return pd.DataFrame()
    
    # Lista para armazenar resultados
    touchpoint_results = []
    
    # Processa cada mensagem individualmente
    for idx, row in tqdm(
        df_subset.iterrows(), 
        total=len(df_subset), 
        desc=f"Classificando mensagens do {actor}"
    ):
        touchpoint = classify_message(row, touchpoints, actor, settings)
        
        result = {
            "Falante": row["Falante"],
            "Mensagem": row["Mensagem"],
            "TOUCHPOINT": touchpoint
        }
        touchpoint_results.append(result)
        
        # Pausa para evitar rate limiting
        time.sleep(settings.rate_limit_delay)
    
    # Converte para DataFrame
    if touchpoint_results:
        return pd.DataFrame(touchpoint_results)
    else:
        logging.warning("Nenhum resultado gerado para o ator %s", actor)
        return pd.DataFrame()


# --------------------------------------------------------------------------- #
# Formatação Final                                                            #
# --------------------------------------------------------------------------- #

def format_final_output(df_dialogue: pd.DataFrame, df_touchpoints: pd.DataFrame) -> pd.DataFrame:
    """Formata o DataFrame final com timestamps START e END."""
    # Primeiro, atualiza ACTIVITY para eventos não-system
    if not df_touchpoints.empty:
        # Remove duplicatas do df_touchpoints
        df_touchpoints_unique = df_touchpoints.drop_duplicates(subset=["Falante", "Mensagem"])
        
        # Para cada linha em df_dialogue que não é system, atualiza ACTIVITY
        for idx, row in df_dialogue.iterrows():
            if row["AGENTE"] != "system":
                # Encontra o touchpoint correspondente
                match = df_touchpoints_unique[
                    (df_touchpoints_unique["Falante"] == row["Falante"]) & 
                    (df_touchpoints_unique["Mensagem"] == row["Mensagem"])
                ]
                if not match.empty:
                    df_dialogue.at[idx, "ACTIVITY"] = match.iloc[0]["TOUCHPOINT"]
    
    # Remove linhas sem ACTIVITY (mensagens não classificadas), exceto system
    df_dialogue = df_dialogue[
        (df_dialogue["ACTIVITY"].notna()) | 
        (df_dialogue["AGENTE"] == "system")
    ]
    
    # Ordena por CASE_ID e EVENT_ID para garantir ordem cronológica
    df_dialogue = df_dialogue.sort_values(["CASE_ID", "EVENT_ID"]).reset_index(drop=True)
    
    # Renomeia TIMESTAMP para END_TIMESTAMP
    df_dialogue["END_TIMESTAMP"] = df_dialogue["TIMESTAMP"]
    
    # Cria coluna START_TIMESTAMP
    df_dialogue["START_TIMESTAMP"] = ""
    
    # Para cada CASE_ID, ajusta os timestamps
    for case_id in df_dialogue["CASE_ID"].unique():
        case_mask = df_dialogue["CASE_ID"] == case_id
        case_indices = df_dialogue[case_mask].index
        
        for i, idx in enumerate(case_indices):
            if df_dialogue.at[idx, "AGENTE"] == "system":
                # Para eventos system, START = END
                df_dialogue.at[idx, "START_TIMESTAMP"] = df_dialogue.at[idx, "END_TIMESTAMP"]
            else:
                # Para eventos reais, START = END do evento anterior
                if i > 0:
                    prev_idx = case_indices[i-1]
                    df_dialogue.at[idx, "START_TIMESTAMP"] = df_dialogue.at[prev_idx, "END_TIMESTAMP"]
                else:
                    # Não deveria acontecer, mas por segurança
                    df_dialogue.at[idx, "START_TIMESTAMP"] = df_dialogue.at[idx, "END_TIMESTAMP"]
    
    # Ajusta AGENTE para "system" ser "syst" (como no exemplo)
    df_dialogue.loc[df_dialogue["AGENTE"] == "system", "AGENTE"] = "syst"
    
    # Seleciona e ordena colunas finais
    df_final = df_dialogue[[
        "CASE_ID", "EVENT_ID", "ACTIVITY", "START_TIMESTAMP", 
        "END_TIMESTAMP", "RECURSO", "AGENTE"
    ]]
    
    return df_final


# --------------------------------------------------------------------------- #
# Entry-point                                                                 #
# --------------------------------------------------------------------------- #

def main() -> None:
    settings = Settings.from_cli()
    configure_logging(settings.log_level)
    logging.info("Iniciando classificação de touchpoints com eventos de sistema")
    logging.info(f"Modelo: {settings.openai_model}")
    logging.info("Processamento: MENSAGEM POR MENSAGEM")

    openai.api_key = get_openai_api_key()

    # Carrega touchpoints
    tp_ai = load_touchpoints(settings.touchpoints_ai_json)
    tp_human = load_touchpoints(settings.touchpoints_human_json)

    # Lê diálogos (JSON único ou ZIP)
    if settings.dialogue_json.suffix.lower() == '.zip':
        logging.info("Lendo diálogos do arquivo ZIP...")
        dialogues = read_dialogues_from_zip(settings.dialogue_json)
    else:
        logging.info("Lendo diálogo do arquivo JSON...")
        dialogues = read_dialogue_json(settings.dialogue_json)
    
    logging.info(f"Total de diálogos encontrados: {len(dialogues)}")
    
    # Converte TODOS os diálogos para DataFrame (já com eventos system)
    df_all_dialogues = convert_dialogues_to_dataframe(dialogues)
    logging.info(f"Total de mensagens (incluindo eventos system): {len(df_all_dialogues)}")
    
    # Lista para armazenar todos os resultados classificados
    all_results = []
    
    # Processa cada diálogo individualmente
    case_ids = df_all_dialogues['CASE_ID'].unique()
    
    for i, case_id in enumerate(case_ids, 1):
        logging.info(f"\nProcessando diálogo {i}/{len(case_ids)}: {case_id}")
        
        # Filtra mensagens deste diálogo específico
        df_dialogue = df_all_dialogues[df_all_dialogues['CASE_ID'] == case_id].copy()
        
        # Conta apenas mensagens reais (não system) para log
        real_messages = df_dialogue[df_dialogue['AGENTE'] != 'system']
        logging.info(f"  Mensagens reais neste diálogo: {len(real_messages)}")
        
        # Processa classificações apenas para mensagens não-system
        df_ai = process_actor(real_messages, "Bot", tp_ai, settings)
        df_human = process_actor(real_messages, "Usuário", tp_human, settings)
        
        # Combina resultados deste diálogo
        dfs_to_concat = []
        if not df_ai.empty:
            dfs_to_concat.append(df_ai)
        if not df_human.empty:
            dfs_to_concat.append(df_human)
        
        if dfs_to_concat:
            df_touchpoints = pd.concat(dfs_to_concat, ignore_index=True)
        else:
            df_touchpoints = pd.DataFrame()
        
        # Formata saída para este diálogo (incluindo eventos system)
        df_result = format_final_output(df_dialogue, df_touchpoints)
        
        all_results.append(df_result)
        logging.info(f"  Eventos totais (com system): {len(df_result)}")
    
    # Concatena todos os resultados
    if all_results:
        df_final = pd.concat(all_results, ignore_index=True)
        # Ordena por EVENT_ID global para manter ordem sequencial
        df_final = df_final.sort_values('EVENT_ID').reset_index(drop=True)
        logging.info(f"\nTotal geral de eventos: {len(df_final)}")
    else:
        logging.error("Nenhuma classificação foi bem-sucedida")
        df_final = pd.DataFrame(columns=[
            "CASE_ID", "EVENT_ID", "ACTIVITY", "START_TIMESTAMP", 
            "END_TIMESTAMP", "RECURSO", "AGENTE"
        ])

    # Salva resultado com separador de ponto e vírgula
    df_final.to_csv(settings.output_csv, index=False, encoding="utf-8-sig", sep=';')
    logging.info("Arquivo '%s' salvo com sucesso!", settings.output_csv)
    
    if not df_final.empty:
        logging.info("\nResumo por conversa:")
        case_counts = df_final['CASE_ID'].value_counts()
        for case_id, count in case_counts.head(10).items():
            # Conta eventos reais e system separadamente
            case_events = df_final[df_final['CASE_ID'] == case_id]
            system_count = len(case_events[case_events['AGENTE'] == 'syst'])
            real_count = count - system_count
            logging.info(f"  {case_id}: {count} eventos totais ({real_count} reais + {system_count} system)")
        if len(case_counts) > 10:
            logging.info(f"  ... e mais {len(case_counts)-10} conversas")
        
        # Mostra range de EVENT_IDs
        logging.info(f"\nEVENT_ID range: {df_final['EVENT_ID'].min()} - {df_final['EVENT_ID'].max()}")
        
        # Mostra contagem de eventos system
        system_events = df_final[df_final['AGENTE'] == 'syst']
        logging.info(f"\nEventos de sistema:")
        logging.info(f"  START-DIALOGUE-SYTEM: {len(system_events[system_events['ACTIVITY'] == 'START-DIALOGUE-SYTEM'])}")
        logging.info(f"  END-DIALOGUE-SYSTEM: {len(system_events[system_events['ACTIVITY'] == 'END-DIALOGUE-SYSTEM'])}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Execução interrompida pelo usuário.")
    except Exception as err:
        logging.exception("Erro não tratado: %s", err)
        sys.exit(1)