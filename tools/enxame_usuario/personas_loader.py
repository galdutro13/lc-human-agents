from __future__ import annotations

import json
import math
import random
import string
from collections import OrderedDict
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


V3_VERSION = "3.0"
REQUIRED_TEMPLATE_FIELDS = {"identidade", "como_agir", "missao"}
ALLOWED_DURATIONS = ("rapida", "media", "lenta")
ALLOWED_OFFSETS = ("horario-comercial", "noite")
ALLOWED_WEEKEND_KEYS = ("false", "true")
OUTPUT_DURATION_KEY = "duração"
LEGACY_REQUIRED_KEYS = ("persona", OUTPUT_DURATION_KEY, "offset", "weekend")


class PersonasLoaderError(ValueError):
    """Raised when a personas file cannot be validated or expanded."""


class MethodologyModel(BaseModel):
    descricao: str
    referencias: list[str]
    seed: int
    n_simulacoes: int
    min_simulacoes_por_persona: int
    metodo: str

    @field_validator("metodo")
    @classmethod
    def validate_method(cls, value: str) -> str:
        if value != "estratificado_proporcional":
            raise ValueError("Only 'estratificado_proporcional' is supported.")
        return value

    @field_validator("n_simulacoes", "min_simulacoes_por_persona")
    @classmethod
    def validate_positive_ints(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Simulation counts must be positive integers.")
        return value


class DistributionBaseModel(BaseModel):
    @staticmethod
    def _validate_probabilities(
        values: Mapping[str, float],
        allowed_keys: Iterable[str],
        label: str,
    ) -> None:
        expected = tuple(allowed_keys)
        actual = tuple(values.keys())
        if set(actual) != set(expected):
            raise ValueError(
                f"{label} keys must be exactly {expected}, got {actual}."
            )

        total = 0.0
        for key, value in values.items():
            if value < 0:
                raise ValueError(f"{label}.{key} must be >= 0.")
            total += value

        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError(f"{label} weights must sum to 1.0, got {total}.")


class DurationDistributionModel(DistributionBaseModel):
    rapida: float
    media: float
    lenta: float

    @model_validator(mode="after")
    def validate_distribution(self) -> "DurationDistributionModel":
        self._validate_probabilities(
            self.model_dump(),
            ALLOWED_DURATIONS,
            "distribuicao_base.duracao",
        )
        return self


class OffsetDistributionModel(DistributionBaseModel):
    horario_comercial: float = Field(alias="horario-comercial")
    noite: float

    @model_validator(mode="after")
    def validate_distribution(self) -> "OffsetDistributionModel":
        self._validate_probabilities(
            self.model_dump(by_alias=True),
            ALLOWED_OFFSETS,
            "distribuicao_base.offset",
        )
        return self


class WeekendDistributionModel(DistributionBaseModel):
    false: float
    true: float

    @model_validator(mode="after")
    def validate_distribution(self) -> "WeekendDistributionModel":
        self._validate_probabilities(
            self.model_dump(),
            ALLOWED_WEEKEND_KEYS,
            "distribuicao_base.weekend",
        )
        return self


class DistributionBundleModel(BaseModel):
    duracao: DurationDistributionModel
    offset: OffsetDistributionModel
    weekend: WeekendDistributionModel


class PersonaAdjustmentsModel(BaseModel):
    duracao: dict[str, float] = Field(default_factory=dict)
    offset: dict[str, float] = Field(default_factory=dict)
    weekend: dict[str, float] = Field(default_factory=dict)

    @staticmethod
    def _validate_adjustments(values: Mapping[str, float], allowed: Iterable[str], label: str) -> None:
        allowed_set = set(allowed)
        for key, value in values.items():
            if key not in allowed_set:
                raise ValueError(f"{label}.{key} is not an allowed category.")
            if value <= 0:
                raise ValueError(f"{label}.{key} must be > 0.")

    @model_validator(mode="after")
    def validate_adjustments(self) -> "PersonaAdjustmentsModel":
        self._validate_adjustments(self.duracao, ALLOWED_DURATIONS, "ajustes.duracao")
        self._validate_adjustments(self.offset, ALLOWED_OFFSETS, "ajustes.offset")
        self._validate_adjustments(self.weekend, ALLOWED_WEEKEND_KEYS, "ajustes.weekend")
        return self


class PersonaDefinitionModel(BaseModel):
    identidade: str
    como_agir: str
    missao: str
    peso_persona: float
    ajustes: PersonaAdjustmentsModel

    @field_validator("peso_persona")
    @classmethod
    def validate_weight(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("peso_persona must be > 0.")
        return value


class PersonasV3Model(BaseModel):
    versao: str
    metodologia: MethodologyModel
    distribuicao_base: DistributionBundleModel
    template_prompt: str
    personas: OrderedDict[str, PersonaDefinitionModel]

    @field_validator("versao")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if value != V3_VERSION:
            raise ValueError(f"Expected versao='{V3_VERSION}'.")
        return value

    @field_validator("template_prompt")
    @classmethod
    def validate_template_prompt(cls, value: str) -> str:
        fields = set()
        for _, field_name, _, _ in string.Formatter().parse(value):
            if field_name:
                fields.add(field_name)
        if fields != REQUIRED_TEMPLATE_FIELDS:
            raise ValueError(
                f"template_prompt must contain exactly {sorted(REQUIRED_TEMPLATE_FIELDS)}."
            )
        return value

    @model_validator(mode="after")
    def validate_minimum_simulations(self) -> "PersonasV3Model":
        persona_count = len(self.personas)
        minimum_total = persona_count * self.metodologia.min_simulacoes_por_persona
        if minimum_total > self.metodologia.n_simulacoes:
            raise ValueError(
                "n_simulacoes must be >= len(personas) * min_simulacoes_por_persona."
            )
        return self


def detect_personas_schema_version(path: str) -> str:
    payload = _read_json_file(path)
    if isinstance(payload, dict) and payload.get("versao") == V3_VERSION:
        return "v3.0"
    if _looks_like_legacy_payload(payload):
        return "v1"
    raise PersonasLoaderError(f"Unsupported personas schema in '{path}'.")


def load_personas_file(path: str, accept_legacy: bool = True) -> dict[str, Any]:
    payload = _read_json_file(path)
    if isinstance(payload, dict) and payload.get("versao") == V3_VERSION:
        return expand_v3_payload(payload)

    if not accept_legacy:
        raise PersonasLoaderError("Legacy v1 personas files are not accepted.")

    if not _looks_like_legacy_payload(payload):
        raise PersonasLoaderError("File does not match legacy v1 schema.")

    return payload


def validate_v3_payload(payload: Mapping[str, Any]) -> PersonasV3Model:
    try:
        return PersonasV3Model.model_validate(payload)
    except ValidationError as exc:
        raise PersonasLoaderError(str(exc)) from exc


def expand_v3_payload(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    schema = validate_v3_payload(payload)
    records = _expand_v3_model(schema)
    return {
        str(index): record
        for index, record in enumerate(records, start=1)
    }


def calculate_adjusted_distribution(
    base_distribution: Mapping[str, float],
    adjustments: Mapping[str, float],
) -> dict[str, float]:
    adjusted = {
        key: float(base_distribution[key]) * float(adjustments.get(key, 1.0))
        for key in base_distribution
    }
    total = sum(adjusted.values())
    if total <= 0:
        raise PersonasLoaderError("Adjusted distribution has zero total weight.")
    return {key: value / total for key, value in adjusted.items()}


def calculate_persona_quotas(
    weights: Mapping[str, float],
    total_simulations: int,
    minimum_per_persona: int,
) -> dict[str, int]:
    if len(weights) * minimum_per_persona > total_simulations:
        raise PersonasLoaderError(
            "Minimum persona coverage exceeds total number of simulations."
        )

    total_weight = sum(weights.values())
    raw_shares = {
        slug: total_simulations * weight / total_weight
        for slug, weight in weights.items()
    }
    quotas = {
        slug: max(minimum_per_persona, math.floor(raw_share))
        for slug, raw_share in raw_shares.items()
    }

    delta = total_simulations - sum(quotas.values())
    if delta > 0:
        remainders = sorted(
            raw_shares,
            key=lambda slug: (raw_shares[slug] - math.floor(raw_shares[slug]), raw_shares[slug]),
            reverse=True,
        )
        for index in range(delta):
            quotas[remainders[index % len(remainders)]] += 1
    elif delta < 0:
        removable = [
            slug for slug in raw_shares
            if quotas[slug] > minimum_per_persona
        ]
        if not removable:
            raise PersonasLoaderError("Unable to reconcile persona quotas to total_simulations.")
        removable = sorted(
            removable,
            key=lambda slug: (raw_shares[slug] - quotas[slug], raw_shares[slug]),
        )
        for index in range(abs(delta)):
            slug = removable[index % len(removable)]
            if quotas[slug] <= minimum_per_persona:
                raise PersonasLoaderError("Quota reconciliation fell below minimum_per_persona.")
            quotas[slug] -= 1
            removable = sorted(
                [candidate for candidate in removable if quotas[candidate] > minimum_per_persona],
                key=lambda candidate: (raw_shares[candidate] - quotas[candidate], raw_shares[candidate]),
            )
            if index < abs(delta) - 1 and not removable:
                raise PersonasLoaderError("Unable to reconcile persona quotas to total_simulations.")

    return quotas


def _expand_v3_model(schema: PersonasV3Model) -> list[dict[str, Any]]:
    base_duration = schema.distribuicao_base.duracao.model_dump()
    base_offset = schema.distribuicao_base.offset.model_dump(by_alias=True)
    base_weekend = schema.distribuicao_base.weekend.model_dump()

    weights = {
        slug: persona.peso_persona
        for slug, persona in schema.personas.items()
    }
    quotas = calculate_persona_quotas(
        weights,
        schema.metodologia.n_simulacoes,
        schema.metodologia.min_simulacoes_por_persona,
    )

    rng = random.Random(schema.metodologia.seed)
    records: list[dict[str, Any]] = []

    for slug, persona in schema.personas.items():
        prompt = schema.template_prompt.format(
            identidade=persona.identidade,
            como_agir=persona.como_agir,
            missao=persona.missao,
        )

        duration_distribution = calculate_adjusted_distribution(
            base_duration,
            persona.ajustes.duracao,
        )
        offset_distribution = calculate_adjusted_distribution(
            base_offset,
            persona.ajustes.offset,
        )
        weekend_distribution = calculate_adjusted_distribution(
            base_weekend,
            persona.ajustes.weekend,
        )

        combo_weights: OrderedDict[tuple[str, str, bool], float] = OrderedDict()
        for duration, offset, weekend_key in product(
            ALLOWED_DURATIONS,
            ALLOWED_OFFSETS,
            ALLOWED_WEEKEND_KEYS,
        ):
            combo_weights[(duration, offset, weekend_key == "true")] = (
                duration_distribution[duration]
                * offset_distribution[offset]
                * weekend_distribution[weekend_key]
            )

        combo_counts = _allocate_largest_remainder(combo_weights, quotas[slug])
        for (duration, offset, weekend), count in combo_counts.items():
            for _ in range(count):
                records.append(
                    {
                        "persona": prompt,
                        OUTPUT_DURATION_KEY: duration,
                        "offset": offset,
                        "weekend": weekend,
                    }
                )

    rng.shuffle(records)
    return records


def _allocate_largest_remainder(
    weighted_items: Mapping[Any, float],
    total_count: int,
) -> OrderedDict[Any, int]:
    total_weight = sum(weighted_items.values())
    if total_weight <= 0:
        raise PersonasLoaderError("Weights must sum to a positive value.")

    raw_counts = {
        key: total_count * weight / total_weight
        for key, weight in weighted_items.items()
    }
    counts = OrderedDict(
        (key, math.floor(raw_counts[key]))
        for key in weighted_items
    )

    remainder = total_count - sum(counts.values())
    priorities = sorted(
        weighted_items,
        key=lambda key: (raw_counts[key] - math.floor(raw_counts[key]), raw_counts[key]),
        reverse=True,
    )
    for index in range(remainder):
        counts[priorities[index % len(priorities)]] += 1

    return counts


def _looks_like_legacy_payload(payload: Any) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False

    for value in payload.values():
        if isinstance(value, str):
            continue
        if not isinstance(value, dict):
            return False
        if set(value.keys()) != set(LEGACY_REQUIRED_KEYS):
            return False
        if not isinstance(value["persona"], str):
            return False
        if value[OUTPUT_DURATION_KEY] not in ALLOWED_DURATIONS:
            return False
        if value["offset"] not in ALLOWED_OFFSETS:
            return False
        if not isinstance(value["weekend"], bool):
            return False
    return True


def _read_json_file(path: str) -> Any:
    file_path = Path(path)
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PersonasLoaderError(f"Personas file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PersonasLoaderError(f"Invalid JSON in personas file '{path}': {exc}") from exc
