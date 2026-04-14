"""Ferramentas de migração entre o schema legado e o schema v3.0."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter
from math import gcd
from pathlib import Path
from typing import Any

from source.simulation_config.sampling import montar_prompt
from source.simulation_config.validation import validar_seed_config

PREFIXO_TEMPLATE = " Siga as duas próximas seções: [[como agir]] e [[missão]]. [[como agir]] "
SEPARADOR_MISSAO = " [[missão]] "
DEFAULT_TEMPLATE_PROMPT = (
    "{identidade} Siga as duas próximas seções: [[como agir]] e [[missão]]. "
    "[[como agir]] {como_agir} [[missão]] {missao}"
)
_NOME_PATTERN = re.compile(r"^Você é (?P<nome>[^,]+),")


def _ordenar_ids_legados(legado: dict[str, Any]) -> list[str]:
    def chave_ordenacao(valor: str) -> tuple[int, str]:
        return (int(valor), valor) if str(valor).isdigit() else (10**12, str(valor))

    return sorted(legado.keys(), key=chave_ordenacao)


def _contagem_ordenada(counter: Counter, ordem: list[str]) -> dict[str, int]:
    return {chave: int(counter[chave]) for chave in ordem if counter[chave] > 0}


def _reduzir_counter(counter: Counter, ordem: list[str]) -> dict[str, int]:
    valores = [int(counter[chave]) for chave in ordem if counter[chave] > 0]
    if not valores:
        raise ValueError("Não é possível reduzir um conjunto vazio de pesos.")

    divisor = valores[0]
    for valor in valores[1:]:
        divisor = gcd(divisor, valor)

    return {chave: int(counter[chave] // divisor) for chave in ordem if counter[chave] > 0}


def _linha_canonica(linha: dict[str, int], ordem: list[str]) -> tuple[tuple[str, int], ...]:
    return tuple((chave, linha[chave]) for chave in ordem if chave in linha)


def _selecionar_default_modal(
    linhas: dict[str, dict[str, int]],
    ordem_personas: list[str],
    ordem_categorias: list[str],
) -> dict[str, int]:
    frequencias: Counter = Counter()
    primeira_ocorrencia: dict[tuple[tuple[str, int], ...], int] = {}

    for indice, persona_id in enumerate(ordem_personas):
        canonica = _linha_canonica(linhas[persona_id], ordem_categorias)
        frequencias[canonica] += 1
        primeira_ocorrencia.setdefault(canonica, indice)

    if not frequencias:
        raise ValueError("Não foi possível identificar uma linha modal.")

    melhor = sorted(
        frequencias.items(),
        key=lambda item: (-item[1], primeira_ocorrencia[item[0]]),
    )[0][0]
    return {chave: valor for chave, valor in melhor}


def _sha256_bytes(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def slugify_persona_name(nome: str) -> str:
    normalizado = unicodedata.normalize("NFKD", nome)
    ascii_only = normalizado.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_only.lower()).strip("_")
    if not slug:
        raise ValueError(f"Não foi possível gerar slug para '{nome}'.")
    return slug


def parse_prompt_monolitico(prompt: str) -> dict[str, str]:
    identidade, separador, restante = prompt.partition(PREFIXO_TEMPLATE)
    if not separador:
        raise ValueError("Prompt legado não contém o prefixo esperado.")

    como_agir, separador_missao, missao = restante.partition(SEPARADOR_MISSAO)
    if not separador_missao:
        raise ValueError("Prompt legado não contém a seção [[missão]] esperada.")

    return {
        "identidade": identidade,
        "como_agir": como_agir,
        "missao": missao,
        "template_prompt": DEFAULT_TEMPLATE_PROMPT,
    }


def _extrair_nome(identidade: str) -> str:
    match = _NOME_PATTERN.match(identidade)
    if not match:
        raise ValueError(f"Não foi possível extrair o nome da identidade: '{identidade}'.")
    return match.group("nome")


def extract_personas_from_legacy(legado: dict[str, dict]) -> tuple[dict[str, dict], list[dict], str]:
    personas: dict[str, dict] = {}
    assinatura_para_slug: dict[tuple[str, str, str], str] = {}
    slugs_usados: set[str] = set()
    entradas: list[dict] = []
    template_prompt: str | None = None

    for entrada_id in _ordenar_ids_legados(legado):
        registro = legado[entrada_id]
        prompt = registro["persona"]
        partes = parse_prompt_monolitico(prompt)
        template_prompt = template_prompt or partes["template_prompt"]

        assinatura = (
            partes["identidade"],
            partes["como_agir"],
            partes["missao"],
        )
        if assinatura not in assinatura_para_slug:
            slug_base = slugify_persona_name(_extrair_nome(partes["identidade"]))
            slug = slug_base
            sufixo = 2
            while slug in slugs_usados:
                slug = f"{slug_base}_{sufixo}"
                sufixo += 1
            slugs_usados.add(slug)
            assinatura_para_slug[assinatura] = slug
            personas[slug] = {
                "identidade": partes["identidade"],
                "como_agir": partes["como_agir"],
                "missao": partes["missao"],
            }

        entradas.append(
            {
                "id": entrada_id,
                "persona_id": assinatura_para_slug[assinatura],
                "persona": prompt,
                "duração": registro["duração"],
                "offset": registro["offset"],
                "weekend": registro["weekend"],
            }
        )

    if template_prompt is None:
        raise ValueError("O legado está vazio; não há template para extrair.")

    return personas, entradas, template_prompt


def auditar_legado(legado: dict[str, dict], source_path: str | None = None) -> dict:
    serializado = json.dumps(legado, ensure_ascii=False, sort_keys=True).encode("utf-8")
    personas_unicas = {registro["persona"] for registro in legado.values()}

    return {
        "source_path": source_path,
        "input_sha256": _sha256_bytes(serializado),
        "entries": len(legado),
        "unique_personas": len(personas_unicas),
        "duracao_counts": dict(sorted(Counter(registro["duração"] for registro in legado.values()).items())),
        "offset_counts": dict(sorted(Counter(registro["offset"] for registro in legado.values()).items())),
        "weekend_counts": {
            chave: int(valor)
            for chave, valor in sorted(
                Counter(str(registro["weekend"]).lower() for registro in legado.values()).items()
            )
        },
    }


def _construir_variaveis_amostragem(
    personas: dict[str, dict],
    entradas: list[dict],
) -> dict[str, dict]:
    ordem_personas = list(personas.keys())
    ordem_duracao = ["rapida", "media", "lenta"]
    ordem_offset = ["horario-comercial", "noite"]
    ordem_weekend = ["true", "false"]

    persona_counter: Counter = Counter()
    duracao_por_persona: dict[str, Counter] = {persona_id: Counter() for persona_id in ordem_personas}
    offset_por_persona: dict[str, Counter] = {persona_id: Counter() for persona_id in ordem_personas}
    weekend_por_offset: dict[str, Counter] = {offset: Counter() for offset in ordem_offset}

    for entrada in entradas:
        persona_id = entrada["persona_id"]
        persona_counter[persona_id] += 1
        duracao_por_persona[persona_id][entrada["duração"]] += 1
        offset_por_persona[persona_id][entrada["offset"]] += 1
        weekend_por_offset[entrada["offset"]][str(entrada["weekend"]).lower()] += 1

    pesos_persona = _reduzir_counter(persona_counter, ordem_personas)
    duracao_reduzida = {
        persona_id: _reduzir_counter(counter, ordem_duracao)
        for persona_id, counter in duracao_por_persona.items()
    }
    offset_reduzido = {
        persona_id: _reduzir_counter(counter, ordem_offset)
        for persona_id, counter in offset_por_persona.items()
    }
    weekend_reduzido = {
        offset: _reduzir_counter(counter, ordem_weekend)
        for offset, counter in weekend_por_offset.items()
    }

    default_duracao = _selecionar_default_modal(duracao_reduzida, ordem_personas, ordem_duracao)
    default_offset = _selecionar_default_modal(offset_reduzido, ordem_personas, ordem_offset)

    pesos_duracao = {"_default": default_duracao}
    for persona_id in ordem_personas:
        if duracao_reduzida[persona_id] != default_duracao:
            pesos_duracao[persona_id] = duracao_reduzida[persona_id]

    pesos_offset = {"_default": default_offset}
    for persona_id in ordem_personas:
        if offset_reduzido[persona_id] != default_offset:
            pesos_offset[persona_id] = offset_reduzido[persona_id]

    return {
        "persona_id": {
            "descricao": "Seleção da persona",
            "tipo": "categorica",
            "depende_de": None,
            "pesos": pesos_persona,
        },
        "duracao": {
            "descricao": "Duração da simulação, condicionada à persona",
            "tipo": "categorica",
            "depende_de": "persona_id",
            "pesos_condicionais": pesos_duracao,
        },
        "offset": {
            "descricao": "Faixa horária, condicionada à persona",
            "tipo": "categorica",
            "depende_de": "persona_id",
            "pesos_condicionais": pesos_offset,
        },
        "weekend": {
            "descricao": "Fim de semana, condicionado ao offset",
            "tipo": "bernoulli",
            "depende_de": "offset",
            "pesos_condicionais": weekend_reduzido,
        },
    }


def construir_config_v3(
    legado: dict[str, dict],
    *,
    n: int = 300,
    seed: int = 42,
    min_por_persona: int = 4,
) -> tuple[dict, dict]:
    personas, entradas, template_prompt = extract_personas_from_legacy(legado)
    variaveis = _construir_variaveis_amostragem(personas, entradas)

    config = {
        "versao": "3.0",
        "personas": personas,
        "template_prompt": template_prompt,
        "amostragem": {
            "n": n,
            "seed": seed,
            "metodo": "ancestral",
            "dag_ordem": ["persona_id", "duracao", "offset", "weekend"],
            "variaveis": variaveis,
            "restricoes": {"min_por_persona": min_por_persona},
        },
    }

    contexto = {
        "personas": personas,
        "entries": entradas,
        "template_prompt": template_prompt,
    }
    return config, contexto


def auditar_reconstrucao_prompts(
    legado: dict[str, dict],
    config_v3: dict,
    entradas: list[dict],
) -> dict:
    personas = config_v3["personas"]
    template = config_v3["template_prompt"]
    unicas_auditadas: dict[str, bool] = {}
    divergencias = []

    for entrada in entradas:
        persona_id = entrada["persona_id"]
        reconstruido = montar_prompt(personas[persona_id], template)
        original = entrada["persona"]
        equivalente = reconstruido.encode("utf-8") == original.encode("utf-8")
        unicas_auditadas.setdefault(persona_id, equivalente)
        if not equivalente:
            divergencias.append(
                {
                    "entry_id": entrada["id"],
                    "persona_id": persona_id,
                    "reconstructed": reconstruido,
                    "original": original,
                }
            )

    return {
        "unique_persona_total": len(unicas_auditadas),
        "unique_persona_matches": sum(1 for valor in unicas_auditadas.values() if valor),
        "entry_total": len(entradas),
        "entry_matches": len(entradas) - len(divergencias),
        "mismatches": divergencias,
    }


def find_first_passing_seed(
    config_v3: dict,
    *,
    start_seed: int = 42,
    max_seed: int = 10_000,
    alfa: float = 0.05,
) -> dict:
    candidato = copy.deepcopy(config_v3)
    for seed in range(start_seed, max_seed + 1):
        candidato["amostragem"]["seed"] = seed
        relatorio = validar_seed_config(candidato, alfa=alfa)
        if relatorio["passou"]:
            return relatorio

    raise ValueError(
        f"Nenhuma seed entre {start_seed} e {max_seed} satisfez os critérios estatísticos."
    )


def migrate_v1_to_v3(
    legado: dict[str, dict],
    *,
    source_path: str | None = None,
    n: int = 300,
    seed: int = 42,
    min_por_persona: int = 4,
    search_seed: bool = True,
    max_seed: int = 10_000,
    alfa: float = 0.05,
) -> tuple[dict, dict]:
    config_v3, contexto = construir_config_v3(
        legado,
        n=n,
        seed=seed,
        min_por_persona=min_por_persona,
    )
    auditoria_prompt = auditar_reconstrucao_prompts(legado, config_v3, contexto["entries"])
    if auditoria_prompt["mismatches"]:
        raise ValueError("A reconstrução dos prompts não foi idêntica ao legado.")

    if search_seed:
        relatorio_seed = find_first_passing_seed(
            config_v3,
            start_seed=seed,
            max_seed=max_seed,
            alfa=alfa,
        )
        config_v3["amostragem"]["seed"] = relatorio_seed["seed"]
    else:
        relatorio_seed = validar_seed_config(config_v3, alfa=alfa)

    relatorio = {
        "legacy_summary": auditar_legado(legado, source_path=source_path),
        "template_prompt": contexto["template_prompt"],
        "personas": {
            "count": len(contexto["personas"]),
            "slugs": list(contexto["personas"].keys()),
        },
        "sampling_summary": {
            "persona_pesos": config_v3["amostragem"]["variaveis"]["persona_id"]["pesos"],
            "duracao_default": config_v3["amostragem"]["variaveis"]["duracao"]["pesos_condicionais"]["_default"],
            "duracao_overrides": sorted(
                chave
                for chave in config_v3["amostragem"]["variaveis"]["duracao"]["pesos_condicionais"].keys()
                if chave != "_default"
            ),
            "offset_default": config_v3["amostragem"]["variaveis"]["offset"]["pesos_condicionais"]["_default"],
            "offset_overrides": sorted(
                chave
                for chave in config_v3["amostragem"]["variaveis"]["offset"]["pesos_condicionais"].keys()
                if chave != "_default"
            ),
            "weekend_condicionais": config_v3["amostragem"]["variaveis"]["weekend"]["pesos_condicionais"],
        },
        "reconstruction_audit": auditoria_prompt,
        "statistical_validation": relatorio_seed,
    }

    return config_v3, relatorio


def load_legacy_json(path: str | Path) -> dict[str, dict]:
    with Path(path).open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)
