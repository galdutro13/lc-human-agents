from __future__ import annotations

import json
import unicodedata
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.enxame_usuario.personas_loader import (
    OUTPUT_DURATION_KEY,
    validate_v3_payload,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
LEGACY_PERSONAS_PATH = ROOT_DIR / "personas_tf.json"
OUTPUT_V3_PATH = ROOT_DIR / "personas_v3.json"
METHODOLOGY_REPORT_PATH = ROOT_DIR / "tools" / "enxame_usuario" / "personas_v3_methodology.md"

PROMPT_PREFIX = " Siga as duas próximas seções: [[como agir]] e [[missão]]. [[como agir]] "
PROMPT_SEPARATOR = " [[missão]] "
FERNANDA_CANONICAL_SNIPPET = "Fale em tom mais baixo, com pausas frequentes"
WEIGHT_2X_SLUGS = {
    "antonia_silveira",
    "camila_rocha",
    "eduardo_martins",
    "fernanda_costa",
    "jose_carlos_da_silva",
}
BASE_DISTRIBUTION = {
    "duracao": {"rapida": 0.27, "media": 0.4167, "lenta": 0.3133},
    "offset": {"horario-comercial": 0.6067, "noite": 0.3933},
    "weekend": {"false": 0.86, "true": 0.14},
}
SHORT_RATIONALES = {
    "ana_beatriz_silva": "Freelancer jovem com rotina mais flexível; leve viés para noite e fim de semana, mantendo duração média.",
    "antonia_silveira": "Perfil idoso, cauteloso e com desconfiança digital; favorece interações lentas e em horário comercial.",
    "camila_rocha": "Empresária objetiva e dinâmica; favorece conversas rápidas e úteis, com menor peso em fins de semana.",
    "carla_mendes": "Gestora analítica com deficiência auditiva; prioriza atendimentos curtos e claros, majoritariamente em dias úteis.",
    "carlos_ferreira": "Busca eficiência para resolver assuntos cotidianos; viés para duração rápida e baixa incidência de fim de semana.",
    "daniela_nascimento": "Perfil organizado e documentado; distribuição moderada com predominância de dias úteis e horário comercial.",
    "eduardo_martins": "Persona técnica e orientada a números; favorece respostas rápidas em contexto profissional.",
    "fernanda_costa": "Caso de renegociação sensível e emocional; aumenta interações lentas e noturnas, com alguma presença em fim de semana.",
    "gabriela_ferreira": "Profissional criativa com demanda prática; mantém viés moderado para horário comercial e dias úteis.",
    "helena_mendonca": "Situação documental delicada e emocionalmente carregada; tende a conversas mais longas e cuidadosas.",
    "jose_carlos_da_silva": "Orçamento apertado e busca por explicações simples; favorece duração média/lenta e algum uso fora do horário comercial.",
    "joao_pedro_oliveira": "Estudante de tecnologia com rotina flexível; reforça noite e fim de semana, sem cenários lentos.",
    "luisa_oliveira": "Estudante e estagiária em início de vida financeira; reforça noite/fim de semana com conversas geralmente médias.",
    "marina_rodrigues": "Médica plantonista com agenda irregular; desloca interações para noite e fim de semana, com respostas rápidas.",
    "miguel_santos": "Caso de acessibilidade técnica exige precisão e paciência; favorece interações lentas e em dias úteis.",
    "patricia_santana": "Advogada com atuação estruturada; mantém interações centradas em horário comercial e dias úteis.",
    "paulo_henrique_almeida": "Caso urgente e indignado; puxa para respostas rápidas e alguma incidência noturna.",
    "rafael_gomes": "Perfil entusiasmado e disperso; mistura respostas rápidas e médias, com maior elasticidade de fim de semana.",
    "ricardo_tanaka": "Executivo metódico e numérico; reforça horário comercial e respostas rápidas em contexto profissional.",
    "roberto_yamamoto": "Consultor processual e regulatório; favorece atendimentos mais longos e em dias úteis.",
}


@dataclass(frozen=True)
class CanonicalPersona:
    slug: str
    nome: str
    first_record_id: int
    record_count: int
    canonical_prompt: str
    fragmentos: dict[str, str]
    variacoes_legadas: list[dict[str, Any]]


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    buffer = []
    last_was_underscore = False
    for char in ascii_only.lower():
        if char.isalnum():
            buffer.append(char)
            last_was_underscore = False
        elif not last_was_underscore:
            buffer.append("_")
            last_was_underscore = True
    return "".join(buffer).strip("_")


def split_prompt(prompt: str) -> dict[str, str]:
    if PROMPT_PREFIX not in prompt or PROMPT_SEPARATOR not in prompt:
        raise ValueError("Prompt does not contain the expected template markers.")

    identidade, remainder = prompt.split(PROMPT_PREFIX, 1)
    como_agir, missao = remainder.split(PROMPT_SEPARATOR, 1)
    return {
        "identidade": identidade,
        "como_agir": como_agir,
        "missao": missao,
    }


def choose_canonical_prompt(slug: str, prompts: Counter[str]) -> str:
    if slug == "fernanda_costa":
        for prompt in prompts:
            if FERNANDA_CANONICAL_SNIPPET in prompt:
                return prompt
        raise ValueError("Unable to find canonical Fernanda Costa prompt variant.")

    most_common = prompts.most_common()
    highest_count = most_common[0][1]
    candidates = sorted(
        prompt for prompt, count in most_common
        if count == highest_count
    )
    return candidates[0]


def compute_adjustments(
    records: list[dict[str, Any]],
    categories: tuple[str, ...],
    base_distribution: dict[str, float],
    value_getter,
) -> dict[str, float]:
    counts = Counter(value_getter(record) for record in records)
    total = len(records)
    alpha = 1.0
    smoothed_total = total + alpha * len(categories)

    adjustments = {}
    for category in categories:
        smoothed_probability = (counts.get(category, 0) + alpha) / smoothed_total
        multiplier = smoothed_probability / base_distribution[category]
        clipped = min(1.8, max(0.6, multiplier))
        adjustments[category] = round(clipped, 2)
    return adjustments


def canonicalize_legacy_dataset(path: Path) -> tuple[list[CanonicalPersona], dict[str, Any]]:
    legacy_payload = json.loads(path.read_text(encoding="utf-8"))
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)

    for record_id, record in legacy_payload.items():
        numeric_id = int(record_id)
        nome = record["persona"].split(",", 1)[0].replace("Você é ", "", 1)
        groups[nome].append((numeric_id, record))

    canonical_personas: list[CanonicalPersona] = []
    anomalies: dict[str, Any] = {
        "legacy_records": len(legacy_payload),
        "nominal_personas": len(groups),
        "unique_prompt_texts": len({record["persona"] for record in legacy_payload.values()}),
        "textual_variants": [],
    }

    for nome, items in sorted(groups.items(), key=lambda item: min(record_id for record_id, _ in item[1])):
        slug = slugify(nome)
        prompts = Counter(record["persona"] for _, record in items)
        canonical_prompt = choose_canonical_prompt(slug, prompts)
        fragmentos = split_prompt(canonical_prompt)

        reconstructed = (
            "{identidade} Siga as duas próximas seções: [[como agir]] e [[missão]]. "
            "[[como agir]] {como_agir} [[missão]] {missao}"
        ).format(**fragmentos)
        if reconstructed != canonical_prompt:
            raise ValueError(f"Prompt round-trip failed for persona '{slug}'.")

        variacoes_legadas = []
        for prompt_text, count in sorted(prompts.items(), key=lambda item: (item[0] != canonical_prompt, item[0])):
            matching_ids = [
                record_id
                for record_id, record in items
                if record["persona"] == prompt_text
            ]
            variacoes_legadas.append(
                {
                    "count": count,
                    "record_ids": matching_ids,
                    "canonical": prompt_text == canonical_prompt,
                    "prompt": prompt_text,
                }
            )

        if len(variacoes_legadas) > 1:
            anomalies["textual_variants"].append(
                {
                    "slug": slug,
                    "nome": nome,
                    "variants": variacoes_legadas,
                }
            )

        canonical_personas.append(
            CanonicalPersona(
                slug=slug,
                nome=nome,
                first_record_id=min(record_id for record_id, _ in items),
                record_count=len(items),
                canonical_prompt=canonical_prompt,
                fragmentos=fragmentos,
                variacoes_legadas=variacoes_legadas,
            )
        )

    return canonical_personas, anomalies


def build_v3_payload(legacy_path: Path = LEGACY_PERSONAS_PATH) -> tuple[dict[str, Any], dict[str, Any]]:
    legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    canonical_personas, anomalies = canonicalize_legacy_dataset(legacy_path)

    canonical_records_by_slug: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in legacy_payload.values():
        nome = record["persona"].split(",", 1)[0].replace("Você é ", "", 1)
        slug = slugify(nome)
        canonical_records_by_slug[slug].append(record)

    personas_section: OrderedDict[str, Any] = OrderedDict()
    adjustment_rows: list[dict[str, Any]] = []
    for canonical_persona in canonical_personas:
        slug = canonical_persona.slug
        records = canonical_records_by_slug[slug]

        ajustes_duracao = compute_adjustments(
            records,
            ("rapida", "media", "lenta"),
            BASE_DISTRIBUTION["duracao"],
            lambda record: record[OUTPUT_DURATION_KEY],
        )
        ajustes_offset = compute_adjustments(
            records,
            ("horario-comercial", "noite"),
            BASE_DISTRIBUTION["offset"],
            lambda record: record["offset"],
        )
        ajustes_weekend = compute_adjustments(
            records,
            ("false", "true"),
            BASE_DISTRIBUTION["weekend"],
            lambda record: str(record["weekend"]).lower(),
        )

        personas_section[slug] = {
            "identidade": canonical_persona.fragmentos["identidade"],
            "como_agir": canonical_persona.fragmentos["como_agir"],
            "missao": canonical_persona.fragmentos["missao"],
            "peso_persona": 2.0 if slug in WEIGHT_2X_SLUGS else 1.0,
            "ajustes": {
                "duracao": ajustes_duracao,
                "offset": ajustes_offset,
                "weekend": ajustes_weekend,
            },
        }
        adjustment_rows.append(
            {
                "slug": slug,
                "peso_persona": personas_section[slug]["peso_persona"],
                "ajustes": personas_section[slug]["ajustes"],
                "racional": SHORT_RATIONALES[slug],
            }
        )

    payload = {
        "versao": "3.0",
        "metodologia": {
            "descricao": (
                "Amostragem estratificada proporcional construída a partir das marginais empíricas do arquivo "
                "legado personas_tf.json (N=300), com deduplicação textual por persona, seed fixa para "
                "reprodutibilidade e piso mínimo de cobertura por persona."
            ),
            "referencias": [
                "Análise empírica do arquivo legado personas_tf.json executada durante a migração v1 -> v3.0.",
                "Decisão metodológica interna: amostragem estratificada proporcional com seed fixa e cobertura mínima por persona.",
            ],
            "seed": 20260331,
            "n_simulacoes": 300,
            "min_simulacoes_por_persona": 12,
            "metodo": "estratificado_proporcional",
        },
        "distribuicao_base": BASE_DISTRIBUTION,
        "template_prompt": (
            "{identidade} Siga as duas próximas seções: [[como agir]] e [[missão]]. "
            "[[como agir]] {como_agir} [[missão]] {missao}"
        ),
        "personas": personas_section,
    }

    validate_v3_payload(payload)

    audit = {
        "summary": {
            "legacy_records": anomalies["legacy_records"],
            "nominal_personas": anomalies["nominal_personas"],
            "unique_prompt_texts": anomalies["unique_prompt_texts"],
        },
        "textual_variants": anomalies["textual_variants"],
        "canonical_personas": [
            {
                "slug": persona.slug,
                "nome": persona.nome,
                "first_record_id": persona.first_record_id,
                "record_count": persona.record_count,
                "peso_persona": payload["personas"][persona.slug]["peso_persona"],
            }
            for persona in canonical_personas
        ],
        "adjustment_rows": adjustment_rows,
    }
    return payload, audit


def write_outputs(
    payload: dict[str, Any],
    audit: dict[str, Any],
    output_path: Path = OUTPUT_V3_PATH,
    report_path: Path = METHODOLOGY_REPORT_PATH,
) -> None:
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(render_methodology_report(audit), encoding="utf-8")


def render_methodology_report(audit: dict[str, Any]) -> str:
    lines = [
        "# Metodologia de Migração das Personas v1 -> v3.0",
        "",
        "## Resumo",
        f"- Registros legados analisados: {audit['summary']['legacy_records']}",
        f"- Personas nominais canônicas: {audit['summary']['nominal_personas']}",
        f"- Textos únicos legados: {audit['summary']['unique_prompt_texts']}",
        "",
        "## Anomalias Legadas",
    ]

    if audit["textual_variants"]:
        for anomaly in audit["textual_variants"]:
            lines.append(f"- `{anomaly['slug']}` ({anomaly['nome']}) possui {len(anomaly['variants'])} variantes textuais.")
            for variant in anomaly["variants"]:
                status = "canônica" if variant["canonical"] else "legada não canônica"
                lines.append(
                    f"  - Variante {status}: {variant['count']} ocorrências, IDs {variant['record_ids']}"
                )
    else:
        lines.append("- Nenhuma anomalia textual encontrada.")

    lines.extend(
        [
            "",
            "## Ajustes por Persona",
        ]
    )
    for row in audit["adjustment_rows"]:
        lines.append(
            f"- `{row['slug']}` | peso={row['peso_persona']} | "
            f"duracao={row['ajustes']['duracao']} | "
            f"offset={row['ajustes']['offset']} | "
            f"weekend={row['ajustes']['weekend']} | "
            f"{row['racional']}"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    payload, audit = build_v3_payload()
    write_outputs(payload, audit)
    print(f"personas_v3.json written to: {OUTPUT_V3_PATH}")
    print(f"methodology report written to: {METHODOLOGY_REPORT_PATH}")


if __name__ == "__main__":
    main()
