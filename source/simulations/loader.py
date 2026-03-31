from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from source.simulations.schema_v3 import ConfigurationDefinition, SimulationDocumentV3


@dataclass(frozen=True)
class ResolvedConfiguration:
    config_id: str
    duracao: str
    periodo: str
    fim_de_semana: bool
    base_config_id: Optional[str] = None


@dataclass(frozen=True)
class ResolvedSimulation:
    sim_id: str
    source_path: str
    source_slug: str
    schema_version: str
    politica_id: str
    persona_id: str
    persona_nome: str
    prompt: str
    config_id: str
    duracao: str
    periodo: str
    fim_de_semana: bool
    prob_alvo: float
    prob_amostragem: float
    peso_analitico: float
    estrato: Optional[str]
    simulation_metadata: dict[str, object]


def load_simulation_document(path: str | Path) -> SimulationDocumentV3:
    raw = Path(path).read_text(encoding="utf-8")
    document = SimulationDocumentV3.model_validate_json(raw)
    validate_simulation_document(document)
    return document


def validate_simulation_document(document: SimulationDocumentV3) -> None:
    for config_id in document.configuracoes:
        _resolve_configuration(config_id, document.configuracoes, set())

    for policy_id, policy in document.politicas_amostrais.items():
        missing_dist_configs = sorted(
            config_id for config_id in policy.distribuicao_alvo.configuracoes if config_id not in document.configuracoes
        )
        if missing_dist_configs:
            raise ValueError(
                f"policy {policy_id} references unknown configs in distribution: {', '.join(missing_dist_configs)}"
            )

        for combo in policy.restricoes.combos_raros_controlados:
            if combo.selector.config_id and combo.selector.config_id not in document.configuracoes:
                raise ValueError(
                    f"policy {policy_id} references unknown config {combo.selector.config_id} in rare combos"
                )

    simulation_ids = set()
    simulations_per_policy: dict[str, int] = {}
    for simulation in document.simulacoes:
        if simulation.id in simulation_ids:
            raise ValueError(f"duplicate simulation id {simulation.id}")
        simulation_ids.add(simulation.id)

        if simulation.persona_id not in document.personas:
            raise ValueError(f"simulation {simulation.id} references unknown persona {simulation.persona_id}")
        if simulation.config_id not in document.configuracoes:
            raise ValueError(f"simulation {simulation.id} references unknown config {simulation.config_id}")
        if simulation.politica_id not in document.politicas_amostrais:
            raise ValueError(f"simulation {simulation.id} references unknown policy {simulation.politica_id}")

        simulations_per_policy[simulation.politica_id] = simulations_per_policy.get(simulation.politica_id, 0) + 1

    for policy_id, policy in document.politicas_amostrais.items():
        expected = policy.n_total
        actual = simulations_per_policy.get(policy_id, 0)
        if expected != actual:
            raise ValueError(f"policy {policy_id} declares n_total={expected} but has {actual} simulations")


def load_simulations(path: str | Path) -> list[ResolvedSimulation]:
    document = load_simulation_document(path)
    source_path = str(Path(path))
    source_slug = Path(path).stem.replace(".v3", "")
    resolved: list[ResolvedSimulation] = []

    for simulation in document.simulacoes:
        persona = document.personas[simulation.persona_id]
        config = _resolve_configuration(simulation.config_id, document.configuracoes, set())
        resolved.append(
            ResolvedSimulation(
                sim_id=simulation.id,
                source_path=source_path,
                source_slug=source_slug,
                schema_version=document.versao_schema,
                politica_id=simulation.politica_id,
                persona_id=simulation.persona_id,
                persona_nome=persona.nome,
                prompt=persona.prompt,
                config_id=simulation.config_id,
                duracao=config.duracao,
                periodo=config.periodo,
                fim_de_semana=config.fim_de_semana,
                prob_alvo=simulation.prob_alvo,
                prob_amostragem=simulation.prob_amostragem,
                peso_analitico=simulation.peso_analitico,
                estrato=simulation.estrato,
                simulation_metadata={
                    "sim_id": simulation.id,
                    "persona_id": simulation.persona_id,
                    "config_id": simulation.config_id,
                    "politica_id": simulation.politica_id,
                    "source_slug": source_slug,
                    "source_path": source_path,
                    "versao_schema": document.versao_schema,
                    "prob_alvo": simulation.prob_alvo,
                    "prob_amostragem": simulation.prob_amostragem,
                    "peso_analitico": simulation.peso_analitico,
                },
            )
        )

    return resolved


def _resolve_configuration(
    config_id: str,
    configurations: dict[str, ConfigurationDefinition],
    stack: set[str],
) -> ResolvedConfiguration:
    if config_id not in configurations:
        raise ValueError(f"unknown configuration {config_id}")
    if config_id in stack:
        cycle = " -> ".join([*stack, config_id])
        raise ValueError(f"configuration inheritance cycle detected: {cycle}")

    config = configurations[config_id]
    if not config.base_config_id:
        if config.duracao is None or config.periodo is None or config.fim_de_semana is None:
            raise ValueError(f"configuration {config_id} is incomplete and has no base_config_id")
        return ResolvedConfiguration(
            config_id=config_id,
            duracao=config.duracao,
            periodo=config.periodo,
            fim_de_semana=config.fim_de_semana,
            base_config_id=config.base_config_id,
        )

    base = _resolve_configuration(config.base_config_id, configurations, { *stack, config_id })
    return ResolvedConfiguration(
        config_id=config_id,
        duracao=config.duracao or base.duracao,
        periodo=config.periodo or base.periodo,
        fim_de_semana=config.fim_de_semana if config.fim_de_semana is not None else base.fim_de_semana,
        base_config_id=config.base_config_id,
    )
