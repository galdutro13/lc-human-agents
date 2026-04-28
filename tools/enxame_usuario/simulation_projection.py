from __future__ import annotations

from datetime import datetime, time as clock_time, timedelta

from source.simulation_config import montar_prompt

OFFSET_ANCHORS = {
    "madrugada": clock_time(hour=3, minute=0),
    "manha": clock_time(hour=9, minute=0),
    "tarde": clock_time(hour=15, minute=0),
    "noite_inicial": clock_time(hour=19, minute=30),
    "noite_tardia": clock_time(hour=23, minute=0),
}

RITMO_CONFIGS = {
    "lento": {"typing_speed": 18.0, "thinking_min": 12.0, "thinking_max": 28.0},
    "medio": {"typing_speed": 42.0, "thinking_min": 4.0, "thinking_max": 11.0},
    "rapido": {"typing_speed": 72.0, "thinking_min": 1.5, "thinking_max": 5.0},
}

CSV_FIELDNAMES = [
    "id",
    "dia_relativo",
    "dia_indice",
    "mes_relativo",
    "semana_relativa",
    "dia_da_semana",
    "dia_do_mes_sintetico",
    "weekend",
    "persona_id",
    "missao_id",
    "offset",
    "ritmo",
    "missao_titulo",
    "missao_categoria",
    "missao_urgencia",
    "missao_complexidade",
    "typing_speed_wpm",
    "thinking_min_seconds",
    "thinking_max_seconds",
    "target_local_datetime",
    "temporal_offset_seconds",
    "prompt_preview",
]


def get_ritmo_parameters(ritmo: str) -> dict[str, float]:
    """Retorna os parâmetros de temporização baseados no ritmo da interação."""
    return RITMO_CONFIGS.get(ritmo, RITMO_CONFIGS["medio"])


def calculate_target_local_datetime(
    dia_relativo: str,
    offset_type: str,
    calendario: dict[str, dict],
    *,
    now: datetime | None = None,
) -> datetime | None:
    """Calcula o datetime local alvo a partir do calendário sintético."""
    if dia_relativo not in calendario or offset_type not in OFFSET_ANCHORS:
        return None

    reference_now = now or datetime.now()
    dia_indice = calendario[dia_relativo]["dia_indice"]
    days_until_next_monday = (7 - reference_now.weekday()) % 7
    base_date = reference_now.date() + timedelta(days=days_until_next_monday)
    target_date = base_date + timedelta(days=dia_indice - 1)
    target_datetime = datetime.combine(target_date, OFFSET_ANCHORS[offset_type])

    if target_datetime <= reference_now:
        target_datetime += timedelta(days=7)

    return target_datetime


def calculate_temporal_offset(
    dia_relativo: str,
    offset_type: str,
    calendario: dict[str, dict],
    *,
    now: datetime | None = None,
) -> timedelta:
    """Calcula o offset temporal determinístico a partir do calendário sintético."""
    reference_now = now or datetime.now()
    target_local_datetime = calculate_target_local_datetime(
        dia_relativo,
        offset_type,
        calendario,
        now=reference_now,
    )
    if target_local_datetime is None:
        return timedelta(0)
    return target_local_datetime - reference_now


def normalize_preview_text(texto: str) -> str:
    """Colapsa whitespace em uma única linha, preservando o conteúdo textual."""
    return " ".join(texto.split())


def truncate_preview(texto: str, max_chars: int) -> str:
    """Trunca o preview quando excede o limite configurado."""
    if max_chars < 4:
        return texto[:max_chars]
    if len(texto) <= max_chars:
        return texto
    return texto[: max_chars - 3].rstrip() + "..."


def resolve_simulation_projection(
    simulacao: dict,
    config: dict,
    *,
    now: datetime | None = None,
    prompt_preview_chars: int = 180,
) -> dict:
    """Resolve prompt, envelopes temporais e colunas enriquecidas de uma simulação."""
    calendario = config["amostragem"]["variaveis"]["dia_relativo"]["calendario"]
    dia_metadata = calendario[simulacao["dia_relativo"]]
    persona = config["personas"][simulacao["persona_id"]]
    missao = config["missoes"][simulacao["missao_id"]]
    prompt = montar_prompt(persona, missao, config["template_prompt"])
    ritmo_params = get_ritmo_parameters(simulacao["ritmo"])
    reference_now = now or datetime.now()
    target_local_datetime = calculate_target_local_datetime(
        simulacao["dia_relativo"],
        simulacao["offset"],
        calendario,
        now=reference_now,
    )
    temporal_offset = calculate_temporal_offset(
        simulacao["dia_relativo"],
        simulacao["offset"],
        calendario,
        now=reference_now,
    )
    prompt_preview = truncate_preview(
        normalize_preview_text(prompt),
        prompt_preview_chars,
    )

    projection = {
        "id": simulacao["id"],
        "dia_relativo": simulacao["dia_relativo"],
        "dia_indice": dia_metadata["dia_indice"],
        "mes_relativo": dia_metadata["mes_relativo"],
        "semana_relativa": dia_metadata["semana_relativa"],
        "dia_da_semana": dia_metadata["dia_da_semana"],
        "dia_do_mes_sintetico": dia_metadata["dia_do_mes_sintetico"],
        "weekend": bool(simulacao["weekend"]),
        "persona_id": simulacao["persona_id"],
        "missao_id": simulacao["missao_id"],
        "offset": simulacao["offset"],
        "ritmo": simulacao["ritmo"],
        "missao_titulo": missao["titulo"],
        "missao_categoria": missao["categoria"],
        "missao_urgencia": missao["urgencia"],
        "missao_complexidade": missao["complexidade"],
        "typing_speed_wpm": ritmo_params["typing_speed"],
        "thinking_min_seconds": ritmo_params["thinking_min"],
        "thinking_max_seconds": ritmo_params["thinking_max"],
        "target_local_datetime": (
            target_local_datetime.isoformat(timespec="seconds")
            if target_local_datetime is not None
            else ""
        ),
        "temporal_offset_seconds": int(temporal_offset.total_seconds()),
        "prompt_preview": prompt_preview,
        "prompt": prompt,
        "thinking_time_range": (
            ritmo_params["thinking_min"],
            ritmo_params["thinking_max"],
        ),
        "temporal_offset": temporal_offset,
    }
    return projection
