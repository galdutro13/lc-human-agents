from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def canonicalize_prompt(prompt: str) -> str:
    normalized = unicodedata.normalize("NFC", prompt).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip()


def extract_persona_name(prompt: str) -> Optional[str]:
    prompt = canonicalize_prompt(prompt)
    if not prompt:
        return None

    first_clause = prompt.split(",", 1)[0].strip()
    match = re.match(r"^Voc\S*\s+é\s+(.+)$", first_clause, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    parts = first_clause.split()
    if len(parts) >= 3 and parts[0].lower().startswith("voc"):
        return " ".join(parts[2:]).strip() or None

    return None


def sanitize_filename_component(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_only)
    sanitized = sanitized.strip("._")
    return sanitized or "unknown"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class PersonaDefinition(StrictModel):
    nome: str
    prompt: str

    @field_validator("nome", "prompt")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be blank")
        return value


class ConfigurationDefinition(StrictModel):
    duracao: Optional[str] = None
    periodo: Optional[str] = None
    fim_de_semana: Optional[bool] = None
    base_config_id: Optional[str] = None

    @field_validator("duracao", "periodo")
    @classmethod
    def non_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("field must not be blank")
        return value


class DistributionTarget(StrictModel):
    fonte: str
    configuracoes: dict[str, float] = Field(default_factory=dict)

    @field_validator("fonte")
    @classmethod
    def fonte_non_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("fonte must not be blank")
        return value

    @field_validator("configuracoes")
    @classmethod
    def validate_probabilities(cls, value: dict[str, float]) -> dict[str, float]:
        for config_id, probability in value.items():
            if probability < 0 or probability > 1:
                raise ValueError(f"invalid probability for config {config_id}")
        total = sum(value.values())
        if value and abs(total - 1.0) > 1e-9:
            raise ValueError("distribution probabilities must sum to 1.0")
        return value


class ComboSelector(StrictModel):
    config_id: Optional[str] = None


class RareComboControl(StrictModel):
    selector: ComboSelector
    min_casos: int = Field(ge=0)
    max_proporcao: float = Field(ge=0, le=1)


class SamplingRestrictions(StrictModel):
    min_por_persona: int = Field(default=0, ge=0)
    min_por_configuracao: int = Field(default=0, ge=0)
    max_proporcao_por_combinacao: float = Field(default=1.0, ge=0, le=1)
    combos_proibidos: list[dict[str, Any]] = Field(default_factory=list)
    combos_raros_controlados: list[RareComboControl] = Field(default_factory=list)


class SamplingComponent(StrictModel):
    nome: str
    proporcao: float = Field(ge=0, le=1)
    base: str

    @field_validator("nome", "base")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be blank")
        return value


class SamplingDefinition(StrictModel):
    tipo: str
    componentes: list[SamplingComponent] = Field(default_factory=list)

    @field_validator("tipo")
    @classmethod
    def tipo_non_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("tipo must not be blank")
        return value

    @model_validator(mode="after")
    def validate_components(self) -> "SamplingDefinition":
        if self.componentes:
            total = sum(component.proporcao for component in self.componentes)
            if abs(total - 1.0) > 1e-9:
                raise ValueError("sampling components must sum to 1.0")
        return self


class SamplingAudit(StrictModel):
    desvio_maximo_aceitavel: float = Field(ge=0)
    repetir_sorteio_se_violado: bool


class SamplingPolicy(StrictModel):
    objetivo: str
    n_total: int = Field(ge=0)
    seed: int = Field(ge=0)
    distribuicao_alvo: DistributionTarget
    restricoes: SamplingRestrictions
    amostragem: SamplingDefinition
    auditoria: SamplingAudit

    @field_validator("objetivo")
    @classmethod
    def objetivo_non_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("objetivo must not be blank")
        return value


class SimulationRecord(StrictModel):
    id: str
    politica_id: str
    persona_id: str
    config_id: str
    estrato: Optional[str] = None
    prob_alvo: float = Field(ge=0, le=1)
    prob_amostragem: float = Field(ge=0, le=1)
    peso_analitico: float = Field(ge=0)

    @field_validator("id", "politica_id", "persona_id", "config_id")
    @classmethod
    def ids_non_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("identifier must not be blank")
        return value


class SimulationDocumentV3(StrictModel):
    versao_schema: str
    personas: dict[str, PersonaDefinition] = Field(default_factory=dict)
    configuracoes: dict[str, ConfigurationDefinition] = Field(default_factory=dict)
    politicas_amostrais: dict[str, SamplingPolicy] = Field(default_factory=dict)
    simulacoes: list[SimulationRecord] = Field(default_factory=list)

    @field_validator("versao_schema")
    @classmethod
    def schema_must_be_3(cls, value: str) -> str:
        if value != "3.0":
            raise ValueError("unsupported schema version")
        return value
