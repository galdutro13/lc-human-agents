#!/usr/bin/env python3
"""
Touchpoint Classifier - JSON Version with System Events (Responses API)

Transforms chatbot dialogues (JSON) into a set of touchpoint classifications,
using the OpenAI **Responses API** to infer a single TOUCHPOINT for each
message according to separate catalogs for bot and user.

Adds artificial system events marking start/end of the dialogue.

Supports single JSON files or ZIP archives containing multiple JSONs.

Configuration:
- Create a .env at project root with: OPENAI_API_KEY=your_key_here

Key implementation notes for the Responses API:
- Uses `from openai import OpenAI` and `OpenAI(api_key=...)`.
- Calls `client.responses.create(model=..., input=..., max_output_tokens=...)`.
- Extracts text with `response.output_text`.

The script follows good engineering practices:
- Modular structure with statically typed functions
- argparse CLI
- Structured logging
- Explicit error handling
- tqdm progress bar
- Docstrings (PEP 257) and PEP 8 compliance (ruff/black friendly)
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
from pathlib import Path
from typing import Dict, List

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# NEW: OpenAI Responses API client
from openai import OpenAI

# --------------------------------------------------------------------------- #
# Global OpenAI client (initialized in main)                                  #
# --------------------------------------------------------------------------- #

CLIENT: OpenAI | None = None


# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Settings:
    """Global script settings."""

    dialogue_json: Path
    touchpoints_ai_json: Path
    touchpoints_human_json: Path
    output_csv: Path
    # You can keep using any supported model here.
    openai_model: str = "gpt-5"
    log_level: str = "INFO"
    rate_limit_delay: float = 0.5  # seconds between calls to avoid rate limits

    @staticmethod
    def from_cli() -> "Settings":
        """Build Settings from CLI arguments."""
        parser = argparse.ArgumentParser(
            description=(
                "Classifica touchpoints em diálogos JSON usando a API da OpenAI (Responses API).\n"
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
        parser.add_argument("--log_level", default="INFO")
        parser.add_argument(
            "--rate_limit_delay",
            type=float,
            default=0.5,
            help="Delay em segundos entre chamadas à API (padrão: 0.5)",
        )
        args = parser.parse_args()

        return Settings(
            dialogue_json=args.dialogue_json,
            touchpoints_ai_json=args.touchpoints_ai_json,
            touchpoints_human_json=args.touchpoints_human_json,
            output_csv=args.output_csv,
            openai_model=args.openai_model,
            log_level=args.log_level.upper(),
            rate_limit_delay=args.rate_limit_delay,
        )


# --------------------------------------------------------------------------- #
# Utilities                                                                   #
# --------------------------------------------------------------------------- #
def configure_logging(level: str = "INFO") -> None:
    """Configure standard logging."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_openai_api_key() -> str:
    """Get API key with priority to .env file."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        api_key_file = os.getenv("OPENAI_API_KEY_FILE")
        if api_key_file and Path(api_key_file).exists():
            api_key = Path(api_key_file).read_text().strip()

    if not api_key:
        raise RuntimeError(
            "OpenAI API key not found. Define 'OPENAI_API_KEY' in a .env file or as an "
            "environment variable, or set 'OPENAI_API_KEY_FILE' pointing to a file with the key."
        )
    return api_key


def parse_timestamp(timestamp_str: str) -> datetime:
    """Convert timestamp string to datetime."""
    try:
        return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            logging.warning(f"Could not parse timestamp: {timestamp_str}")
            return datetime.now()


def subtract_one_second(timestamp_str: str) -> str:
    """Subtract one second from a timestamp string."""
    dt = parse_timestamp(timestamp_str)
    dt_minus_one = dt - timedelta(seconds=1)
    return dt_minus_one.isoformat()


# --------------------------------------------------------------------------- #
# Dialogue reading                                                             #
# --------------------------------------------------------------------------- #
def read_dialogue_json(json_path: Path) -> List[Dict]:
    """Read a dialogue JSON file and return a list of dialogues."""
    with json_path.open(encoding="utf-8") as fp:
        data = json.load(fp)
    if isinstance(data, dict) and "messages" in data:
        return [data]
    return data


def read_dialogues_from_zip(zip_path: Path) -> List[Dict]:
    """Read multiple dialogue JSON files from a ZIP archive."""
    dialogues: List[Dict] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for filename in zf.namelist():
            if filename.endswith(".json"):
                with zf.open(filename) as f:
                    content = f.read().decode("utf-8")
                    data = json.loads(content)
                    if isinstance(data, dict) and "messages" in data:
                        dialogues.append(data)
                    elif isinstance(data, list):
                        dialogues.extend(data)
    return dialogues


def convert_dialogues_to_dataframe(dialogues: List[Dict]) -> pd.DataFrame:
    """Convert a list of dialogue JSONs to a DataFrame (injecting system events)."""
    rows: List[Dict] = []
    global_event_id = 0

    for dialogue in dialogues:
        thread_id = dialogue.get("thread_id", "unknown")
        messages = sorted(dialogue.get("messages", []), key=lambda x: x.get("index", 0))

        # START-DIALOGUE-SYTEM (typo kept for compatibility)
        if messages:
            first_timestamp = None
            for msg in messages:
                if msg["type"] == "ai":
                    first_timestamp = msg.get("timing_metadata", {}).get("banco_generation_timestamp")
                else:
                    first_timestamp = msg.get("simulated_timestamp")
                if first_timestamp:
                    break

            if first_timestamp:
                start_timestamp = subtract_one_second(first_timestamp)
                rows.append(
                    {
                        "CASE_ID": thread_id,
                        "EVENT_ID": global_event_id,
                        "INTERNAL_INDEX": -1,
                        "Falante": "system",
                        "Mensagem": "",
                        "TIMESTAMP": start_timestamp,
                        "RECURSO": "",
                        "AGENTE": "system",
                        "ACTIVITY": "START-DIALOGUE-SYTEM",
                    }
                )
                global_event_id += 1

        # Real messages
        for msg in messages:
            timestamp = (
                msg.get("timing_metadata", {}).get("banco_generation_timestamp")
                if msg["type"] == "ai"
                else msg.get("simulated_timestamp")
            )
            if not timestamp:
                timestamp = msg.get("simulated_timestamp", "")

            rag_sources = msg.get("rag_datasources", [])
            rag_sources_str = ", ".join(rag_sources) if rag_sources else ""

            rows.append(
                {
                    "CASE_ID": thread_id,
                    "EVENT_ID": global_event_id,
                    "INTERNAL_INDEX": msg.get("index", 0),
                    "Falante": "Bot" if msg["type"] == "ai" else "Usuário",
                    "Mensagem": msg.get("content", ""),
                    "TIMESTAMP": timestamp,
                    "RECURSO": rag_sources_str,
                    "AGENTE": msg["type"],
                    "ACTIVITY": None,  # to be filled later
                }
            )
            global_event_id += 1

        # END-DIALOGUE-SYSTEM
        if messages:
            last_timestamp = rows[-1]["TIMESTAMP"] if rows else None
            if last_timestamp:
                rows.append(
                    {
                        "CASE_ID": thread_id,
                        "EVENT_ID": global_event_id,
                        "INTERNAL_INDEX": 999999,
                        "Falante": "system",
                        "Mensagem": "",
                        "TIMESTAMP": last_timestamp,
                        "RECURSO": "",
                        "AGENTE": "system",
                        "ACTIVITY": "END-DIALOGUE-SYSTEM",
                    }
                )
                global_event_id += 1

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Classification                                                              #
# --------------------------------------------------------------------------- #
def load_touchpoints(path: Path) -> List[str]:
    """Load a touchpoint catalog from an array-based JSON file."""
    with path.open(encoding="utf-8") as fp:
        data = json.load(fp)

    if isinstance(data, list):
        return [item.get("subtipo", "") for item in data if "subtipo" in item]

    if isinstance(data, dict):
        all_subtipos: List[str] = []
        for sublist in data.values():
            if isinstance(sublist, list):
                all_subtipos.extend(sublist)
        return all_subtipos

    return []


def build_prompt(message: pd.Series, touchpoints: List[str], actor: str) -> str:
    """Build a single-message classification prompt."""
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
    message: pd.Series, touchpoints: List[str], actor: str, settings: Settings
) -> str:
    """Classify ONE message using the OpenAI Responses API."""
    assert CLIENT is not None, "OpenAI client not initialized"
    prompt = build_prompt(message, touchpoints, actor)

    try:
        # --- Responses API call (non-streaming) ---
        response = CLIENT.responses.create(
            model=settings.openai_model,
            input=prompt,  # simple text input is sufficient here
            max_output_tokens=100,  # short answer expected
        )

        # Extract the plain text
        touchpoint = (response.output_text or "").strip()

        # Sanitize & validate against the catalog (case-insensitive)
        touchpoint = touchpoint.replace('"', "").replace("'", "").strip()
        tp_upper = [tp.upper() for tp in touchpoints]
        if touchpoint.upper() not in tp_upper:
            logging.warning(f"Unrecognized touchpoint: {touchpoint}")
            return ""

        return touchpoint.upper()

    except Exception as e:
        logging.error(f"Error classifying message: {e}")
        return ""


def process_actor(
    df: pd.DataFrame, actor: str, touchpoints: List[str], settings: Settings
) -> pd.DataFrame:
    """Process all messages for one actor, one by one."""
    df_subset = df[df["Falante"] == actor].copy()
    if len(df_subset) == 0:
        return pd.DataFrame()

    results: List[Dict[str, str]] = []

    for _, row in tqdm(
        df_subset.iterrows(),
        total=len(df_subset),
        desc=f"Classificando mensagens do {actor}",
    ):
        touchpoint = classify_message(row, touchpoints, actor, settings)
        results.append(
            {"Falante": row["Falante"], "Mensagem": row["Mensagem"], "TOUCHPOINT": touchpoint}
        )
        time.sleep(settings.rate_limit_delay)

    return pd.DataFrame(results) if results else pd.DataFrame()


# --------------------------------------------------------------------------- #
# Final formatting                                                            #
# --------------------------------------------------------------------------- #
def format_final_output(df_dialogue: pd.DataFrame, df_touchpoints: pd.DataFrame) -> pd.DataFrame:
    """Format the final DataFrame, injecting START/END timestamps and selecting columns."""
    if not df_touchpoints.empty:
        df_touchpoints_unique = df_touchpoints.drop_duplicates(subset=["Falante", "Mensagem"])
        for idx, row in df_dialogue.iterrows():
            if row["AGENTE"] != "system":
                match = df_touchpoints_unique[
                    (df_touchpoints_unique["Falante"] == row["Falante"])
                    & (df_touchpoints_unique["Mensagem"] == row["Mensagem"])
                ]
                if not match.empty:
                    df_dialogue.at[idx, "ACTIVITY"] = match.iloc[0]["TOUCHPOINT"]

    df_dialogue = df_dialogue[
        (df_dialogue["ACTIVITY"].notna()) | (df_dialogue["AGENTE"] == "system")
    ]

    df_dialogue = df_dialogue.sort_values(["CASE_ID", "EVENT_ID"]).reset_index(drop=True)

    df_dialogue["END_TIMESTAMP"] = df_dialogue["TIMESTAMP"]
    df_dialogue["START_TIMESTAMP"] = ""

    for case_id in df_dialogue["CASE_ID"].unique():
        mask = df_dialogue["CASE_ID"] == case_id
        indices = df_dialogue[mask].index

        for i, idx in enumerate(indices):
            if df_dialogue.at[idx, "AGENTE"] == "system":
                df_dialogue.at[idx, "START_TIMESTAMP"] = df_dialogue.at[idx, "END_TIMESTAMP"]
            else:
                if i > 0:
                    prev_idx = indices[i - 1]
                    df_dialogue.at[idx, "START_TIMESTAMP"] = df_dialogue.at[prev_idx, "END_TIMESTAMP"]
                else:
                    df_dialogue.at[idx, "START_TIMESTAMP"] = df_dialogue.at[idx, "END_TIMESTAMP"]

    # Adjust "system" to "syst" to match your downstream example
    df_dialogue.loc[df_dialogue["AGENTE"] == "system", "AGENTE"] = "syst"

    df_final = df_dialogue[
        ["CASE_ID", "EVENT_ID", "ACTIVITY", "START_TIMESTAMP", "END_TIMESTAMP", "RECURSO", "AGENTE"]
    ]
    return df_final


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #
def main() -> None:
    settings = Settings.from_cli()
    configure_logging(settings.log_level)
    logging.info("Iniciando classificação de touchpoints com eventos de sistema (Responses API)")
    logging.info(f"Modelo: {settings.openai_model}")
    logging.info("Processamento: MENSAGEM POR MENSAGEM")

    # Initialize the OpenAI client (Responses API)
    api_key = get_openai_api_key()
    global CLIENT
    CLIENT = OpenAI(api_key=api_key)

    # Load catalogs
    tp_ai = load_touchpoints(settings.touchpoints_ai_json)
    tp_human = load_touchpoints(settings.touchpoints_human_json)

    # Read dialogues (JSON single or ZIP)
    if settings.dialogue_json.suffix.lower() == ".zip":
        logging.info("Lendo diálogos do arquivo ZIP...")
        dialogues = read_dialogues_from_zip(settings.dialogue_json)
    else:
        logging.info("Lendo diálogo do arquivo JSON...")
        dialogues = read_dialogue_json(settings.dialogue_json)

    logging.info(f"Total de diálogos encontrados: {len(dialogues)}")

    # Convert ALL dialogues to a DataFrame (already with system events)
    df_all_dialogues = convert_dialogues_to_dataframe(dialogues)
    logging.info(f"Total de mensagens (incluindo eventos system): {len(df_all_dialogues)}")

    all_results: List[pd.DataFrame] = []

    case_ids = df_all_dialogues["CASE_ID"].unique()
    for i, case_id in enumerate(case_ids, 1):
        logging.info(f"\nProcessando diálogo {i}/{len(case_ids)}: {case_id}")
        df_dialogue = df_all_dialogues[df_all_dialogues["CASE_ID"] == case_id].copy()

        real_messages = df_dialogue[df_dialogue["AGENTE"] != "system"]
        logging.info(f"  Mensagens reais neste diálogo: {len(real_messages)}")

        df_ai = process_actor(real_messages, "Bot", tp_ai, settings)
        df_human = process_actor(real_messages, "Usuário", tp_human, settings)

        dfs_to_concat: List[pd.DataFrame] = []
        if not df_ai.empty:
            dfs_to_concat.append(df_ai)
        if not df_human.empty:
            dfs_to_concat.append(df_human)

        df_touchpoints = pd.concat(dfs_to_concat, ignore_index=True) if dfs_to_concat else pd.DataFrame()
        df_result = format_final_output(df_dialogue, df_touchpoints)

        all_results.append(df_result)
        logging.info(f"  Eventos totais (com system): {len(df_result)}")

    if all_results:
        df_final = pd.concat(all_results, ignore_index=True)
        df_final = df_final.sort_values("EVENT_ID").reset_index(drop=True)
        logging.info(f"\nTotal geral de eventos: {len(df_final)}")
    else:
        logging.error("Nenhuma classificação foi bem-sucedida")
        df_final = pd.DataFrame(
            columns=["CASE_ID", "EVENT_ID", "ACTIVITY", "START_TIMESTAMP", "END_TIMESTAMP", "RECURSO", "AGENTE"]
        )

    df_final.to_csv(settings.output_csv, index=False, encoding="utf-8-sig", sep=";")
    logging.info("Arquivo '%s' salvo com sucesso!", settings.output_csv)

    if not df_final.empty:
        logging.info("\nResumo por conversa:")
        case_counts = df_final["CASE_ID"].value_counts()
        for case_id, count in case_counts.head(10).items():
            case_events = df_final[df_final["CASE_ID"] == case_id]
            system_count = len(case_events[case_events["AGENTE"] == "syst"])
            real_count = count - system_count
            logging.info(f"  {case_id}: {count} eventos totais ({real_count} reais + {system_count} system)")
        if len(case_counts) > 10:
            logging.info(f"  ... e mais {len(case_counts) - 10} conversas")

        logging.info(f"\nEVENT_ID range: {df_final['EVENT_ID'].min()} - {df_final['EVENT_ID'].max()}")

        system_events = df_final[df_final["AGENTE"] == "syst"]
        logging.info("\nEventos de sistema:")
        logging.info(
            "  START-DIALOGUE-SYTEM: %d",
            len(system_events[system_events["ACTIVITY"] == "START-DIALOGUE-SYTEM"]),
        )
        logging.info(
            "  END-DIALOGUE-SYSTEM: %d",
            len(system_events[system_events["ACTIVITY"] == "END-DIALOGUE-SYSTEM"]),
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Execução interrompida pelo usuário.")
    except Exception as err:
        logging.exception("Erro não tratado: %s", err)
        sys.exit(1)
