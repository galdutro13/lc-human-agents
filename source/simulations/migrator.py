from __future__ import annotations

import difflib
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from source.simulations.loader import load_simulation_document, load_simulations, validate_simulation_document
from source.simulations.schema_v3 import (
    ConfigurationDefinition,
    PersonaDefinition,
    SamplingAudit,
    SamplingComponent,
    SamplingDefinition,
    SamplingPolicy,
    SamplingRestrictions,
    SimulationDocumentV3,
    SimulationRecord,
    canonicalize_prompt,
    extract_persona_name,
    sanitize_filename_component,
)


def write_simulation_schema(output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = SimulationDocumentV3.model_json_schema()
    target.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def migrate_legacy_file(source_path: str | Path, output_dir: str | Path) -> dict[str, Path]:
    source = Path(source_path)
    output_base = Path(output_dir)
    output_base.mkdir(parents=True, exist_ok=True)

    raw_text = source.read_text(encoding="utf-8")
    raw_data = json.loads(raw_text)
    source_slug = sanitize_filename_component(source.stem.lower())
    file_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    if not isinstance(raw_data, dict):
        raise ValueError(f"legacy file {source} must have dict as top-level structure")

    if _is_legacy_simulation_map(raw_data):
        document, manifest, id_map, semantic_diff = _migrate_simulation_map(raw_data, source.name, source_slug, file_hash)
    elif _is_prompt_catalog(raw_data):
        document, manifest, id_map, semantic_diff = _migrate_prompt_catalog(raw_data, source.name, source_slug, file_hash)
    else:
        raise ValueError(f"unsupported legacy structure in {source}")

    validate_simulation_document(document)
    resolved = load_simulations_from_document(document, source)
    validation_report = _build_validation_report(document, resolved)

    target_dir = output_base / source_slug
    target_dir.mkdir(parents=True, exist_ok=True)

    document_path = target_dir / f"{source_slug}.v3.json"
    manifest_path = target_dir / "migration_manifest.json"
    id_map_path = target_dir / "id_map.json"
    validation_path = target_dir / "validation_report.json"
    semantic_diff_path = target_dir / "semantic_diff_report.json"
    schema_path = output_base / "simulation_schema_v3.json"

    document_path.write_text(
        json.dumps(document.model_dump(exclude_none=True), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    id_map_path.write_text(json.dumps(id_map, indent=2, ensure_ascii=False), encoding="utf-8")
    validation_path.write_text(json.dumps(validation_report, indent=2, ensure_ascii=False), encoding="utf-8")
    semantic_diff_path.write_text(json.dumps(semantic_diff, indent=2, ensure_ascii=False), encoding="utf-8")
    write_simulation_schema(schema_path)

    return {
        "document": document_path,
        "manifest": manifest_path,
        "id_map": id_map_path,
        "validation": validation_path,
        "semantic_diff": semantic_diff_path,
        "schema": schema_path,
    }


def load_simulations_from_document(document: SimulationDocumentV3, source_path: Path) -> list[dict[str, Any]]:
    temp_path = source_path.parent / f".__tmp__{source_path.stem}.v3.json"
    temp_path.write_text(json.dumps(document.model_dump(exclude_none=True), ensure_ascii=False), encoding="utf-8")
    try:
        return [simulation.simulation_metadata for simulation in load_simulations(temp_path)]
    finally:
        temp_path.unlink(missing_ok=True)


def _is_legacy_simulation_map(raw_data: dict[str, Any]) -> bool:
    if not raw_data:
        return True
    return all(isinstance(value, dict) for value in raw_data.values())


def _is_prompt_catalog(raw_data: dict[str, Any]) -> bool:
    return bool(raw_data) and all(isinstance(value, str) for value in raw_data.values())


def _migrate_simulation_map(
    raw_data: dict[str, dict[str, Any]],
    source_name: str,
    source_slug: str,
    file_hash: str,
) -> tuple[SimulationDocumentV3, dict[str, Any], dict[str, Any], dict[str, Any]]:
    personas: dict[str, PersonaDefinition] = {}
    configuracoes: dict[str, ConfigurationDefinition] = {}
    simulacoes: list[SimulationRecord] = []
    id_map: dict[str, Any] = {"simulacoes": {}}
    anomalies: list[dict[str, Any]] = []
    prompt_index: dict[str, str] = {}

    for sim_id, record in raw_data.items():
        prompt = record.get("persona")
        duracao = record.get("duração")
        periodo = record.get("offset")
        fim_de_semana = record.get("weekend")
        if not isinstance(prompt, str):
            raise ValueError(f"simulation {sim_id} missing persona string")
        if not isinstance(duracao, str) or not isinstance(periodo, str) or not isinstance(fim_de_semana, bool):
            raise ValueError(f"simulation {sim_id} has invalid legacy configuration fields")

        canonical_prompt = canonicalize_prompt(prompt)
        persona_hash = hashlib.sha256(canonical_prompt.encode("utf-8")).hexdigest()[:16]
        persona_id = f"per::{source_slug}::{persona_hash}"

        existing_hash_prompt = prompt_index.get(persona_id)
        if existing_hash_prompt and existing_hash_prompt != canonical_prompt:
            raise ValueError(f"persona collision detected for {persona_id}")
        prompt_index[persona_id] = canonical_prompt

        if persona_id not in personas:
            extracted_name = extract_persona_name(prompt)
            if not extracted_name:
                extracted_name = f"Persona {persona_hash}"
                anomalies.append(
                    {
                        "type": "missing_persona_name",
                        "severity": "warning",
                        "persona_id": persona_id,
                        "message": "Nome não extraído automaticamente; placeholder aplicado.",
                    }
                )
            personas[persona_id] = PersonaDefinition(nome=extracted_name, prompt=prompt)

        config_id = _build_config_id(duracao, periodo, fim_de_semana)
        configuracoes.setdefault(
            config_id,
            ConfigurationDefinition(
                duracao=duracao,
                periodo=periodo,
                fim_de_semana=fim_de_semana,
            ),
        )

        id_map["simulacoes"][sim_id] = {
            "sim_id": str(sim_id),
            "persona_id": persona_id,
            "config_id": config_id,
        }

    config_distribution = Counter()
    for mapping in id_map["simulacoes"].values():
        config_distribution[mapping["config_id"]] += 1

    politica_id = f"pol::{source_slug}::derived-freq-v1"
    total_simulations = len(raw_data)
    distribution_probs = {
        config_id: count / total_simulations
        for config_id, count in sorted(config_distribution.items())
    } if total_simulations else {}
    seed = int(file_hash[:8], 16)

    policy = SamplingPolicy(
        objetivo=(
            f"Política derivada automaticamente do legado {source_name} "
            "a partir das frequências observadas por configuração."
        ),
        n_total=total_simulations,
        seed=seed,
        distribuicao_alvo={
            "fonte": f"frequencias_observadas::{source_name}::{file_hash[:12]}",
            "configuracoes": distribution_probs,
        },
        restricoes=SamplingRestrictions(
            min_por_persona=0,
            min_por_configuracao=0,
            max_proporcao_por_combinacao=1.0,
            combos_proibidos=[],
            combos_raros_controlados=[],
        ),
        amostragem=SamplingDefinition(
            tipo="mistura_ponderada_estratificada",
            componentes=[
                SamplingComponent(
                    nome="naturalistica",
                    proporcao=1.0,
                    base="distribuicao_alvo",
                )
            ],
        ),
        auditoria=SamplingAudit(
            desvio_maximo_aceitavel=0.02,
            repetir_sorteio_se_violado=True,
        ),
    )

    for sim_id, mapping in raw_data.items():
        config_id = id_map["simulacoes"][sim_id]["config_id"]
        probability = distribution_probs.get(config_id, 0.0)
        simulacoes.append(
            SimulationRecord(
                id=str(sim_id),
                politica_id=politica_id,
                persona_id=id_map["simulacoes"][sim_id]["persona_id"],
                config_id=config_id,
                prob_alvo=probability,
                prob_amostragem=probability,
                peso_analitico=1.0,
            )
        )

    anomalies.extend(_detect_near_duplicate_prompts(personas))

    document = SimulationDocumentV3(
        versao_schema="3.0",
        personas=personas,
        configuracoes=configuracoes,
        politicas_amostrais={politica_id: policy},
        simulacoes=simulacoes,
    )

    manifest = {
        "source_file": source_name,
        "source_slug": source_slug,
        "source_sha256": file_hash,
        "migration_mode": "legacy_simulation_map",
        "summary": {
            "legacy_simulations": len(raw_data),
            "personas_unique": len(personas),
            "configuracoes_unique": len(configuracoes),
            "politicas_unique": 1,
        },
        "defaults_applied": [
            "versao_schema=3.0",
            "restricoes sem restrições deriváveis foram iniciadas vazias",
            "amostragem naturalistica com proporcao 1.0 derivada da distribuicao_alvo",
            "prob_amostragem igual a prob_alvo por falta de probabilidade histórica individual",
            "peso_analitico=1.0 por default determinístico",
        ],
        "human_review_required": [
            "Revisar redação metodológica de objetivo/fonte da política amostral para uso em artigo.",
            "Revisar anomalias de prompts quase duplicados antes de qualquer consolidação editorial.",
        ],
        "anomalies": anomalies,
    }

    semantic_diff = {
        "source_file": source_name,
        "preserved_fields": {
            "sim_ids_preserved": sorted(str(sim_id) for sim_id in raw_data.keys()),
            "all_prompts_preserved": True,
            "all_configurations_preserved": True,
        },
        "counts": {
            "legacy_simulations": len(raw_data),
            "migrated_simulations": len(simulacoes),
            "legacy_unique_personas": len({canonicalize_prompt(record["persona"]) for record in raw_data.values()}),
            "migrated_unique_personas": len(personas),
            "legacy_unique_configurations": len(
                {(record["duração"], record["offset"], record["weekend"]) for record in raw_data.values()}
            ),
            "migrated_unique_configurations": len(configuracoes),
        },
    }

    return document, manifest, id_map, semantic_diff


def _migrate_prompt_catalog(
    raw_data: dict[str, str],
    source_name: str,
    source_slug: str,
    file_hash: str,
) -> tuple[SimulationDocumentV3, dict[str, Any], dict[str, Any], dict[str, Any]]:
    personas: dict[str, PersonaDefinition] = {}
    id_map: dict[str, Any] = {"prompt_catalog": {}}
    anomalies: list[dict[str, Any]] = [
        {
            "type": "partial_migration",
            "severity": "warning",
            "message": (
                "Arquivo legado contém apenas catálogo de prompts; configuracoes, politicas_amostrais "
                "e simulacoes foram deixadas vazias por não serem inferíveis automaticamente."
            ),
        }
    ]

    for legacy_id, prompt in raw_data.items():
        canonical_prompt = canonicalize_prompt(prompt)
        persona_hash = hashlib.sha256(canonical_prompt.encode("utf-8")).hexdigest()[:16]
        persona_id = f"per::{source_slug}::{persona_hash}"
        if persona_id not in personas:
            extracted_name = extract_persona_name(prompt) or f"Persona {persona_hash}"
            personas[persona_id] = PersonaDefinition(nome=extracted_name, prompt=prompt)
        id_map["prompt_catalog"][legacy_id] = {"persona_id": persona_id}

    document = SimulationDocumentV3(
        versao_schema="3.0",
        personas=personas,
        configuracoes={},
        politicas_amostrais={},
        simulacoes=[],
    )

    manifest = {
        "source_file": source_name,
        "source_slug": source_slug,
        "source_sha256": file_hash,
        "migration_mode": "prompt_catalog_partial",
        "summary": {
            "legacy_entries": len(raw_data),
            "personas_unique": len(personas),
            "configuracoes_unique": 0,
            "politicas_unique": 0,
            "simulacoes_unique": 0,
        },
        "defaults_applied": [
            "versao_schema=3.0",
            "configuracoes={} porque o legado não fornece duração/período/fim de semana",
            "politicas_amostrais={} porque o legado não fornece desenho amostral",
            "simulacoes=[] porque o legado não descreve instâncias executáveis completas",
        ],
        "human_review_required": [
            "Decidir se este catálogo deve ser enriquecido manualmente para se tornar uma fonte executável de simulações.",
        ],
        "anomalies": anomalies,
    }

    semantic_diff = {
        "source_file": source_name,
        "preserved_fields": {
            "all_prompts_preserved": True,
            "simulations_generated": False,
        },
        "counts": {
            "legacy_entries": len(raw_data),
            "migrated_personas": len(personas),
            "migrated_simulacoes": 0,
        },
    }

    return document, manifest, id_map, semantic_diff


def _build_validation_report(document: SimulationDocumentV3, resolved_metadata: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": document.versao_schema,
        "status": "ok",
        "checks": {
            "schema_validation": True,
            "referential_integrity": True,
            "resolved_simulations_count": len(resolved_metadata),
            "simulacoes_count": len(document.simulacoes),
            "personas_count": len(document.personas),
            "configuracoes_count": len(document.configuracoes),
            "politicas_count": len(document.politicas_amostrais),
        },
    }


def _build_config_id(duracao: str, periodo: str, fim_de_semana: bool) -> str:
    weekend_code = "we" if fim_de_semana else "wd"
    return f"cfg::{duracao}::{periodo}::{weekend_code}"


def _detect_near_duplicate_prompts(personas: dict[str, PersonaDefinition]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    persona_items = list(personas.items())
    for index, (persona_id, persona) in enumerate(persona_items):
        left = canonicalize_prompt(persona.prompt)
        for other_id, other_persona in persona_items[index + 1:]:
            right = canonicalize_prompt(other_persona.prompt)
            ratio = difflib.SequenceMatcher(None, left, right).ratio()
            if ratio >= 0.995:
                anomalies.append(
                    {
                        "type": "near_duplicate_prompt",
                        "severity": "warning",
                        "persona_id": persona_id,
                        "other_persona_id": other_id,
                        "similarity_ratio": round(ratio, 6),
                    }
                )
    return anomalies
