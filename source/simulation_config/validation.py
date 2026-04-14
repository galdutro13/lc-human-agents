"""Validação estatística da amostra gerada pelo schema v3.0."""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
from scipy.stats import chisquare

from source.simulation_config.sampling import gerar_simulacoes


def _normalizar_observado(valor) -> str:
    if isinstance(valor, bool):
        return str(valor).lower()
    return str(valor)


def _normalizar_pesos(pesos: dict[str, float]) -> dict[str, float]:
    total = sum(float(valor) for valor in pesos.values())
    if total <= 0:
        raise ValueError("A soma dos pesos esperados deve ser positiva.")
    return {chave: float(valor) / total for chave, valor in pesos.items()}


def _dominio_da_variavel(spec: dict) -> list[str]:
    if spec.get("depende_de") is None:
        return list(spec["pesos"].keys())

    categorias: list[str] = []
    vistos = set()
    for chave_condicional, pesos in spec["pesos_condicionais"].items():
        if chave_condicional == "_default":
            continue
        for categoria in pesos.keys():
            if categoria not in vistos:
                vistos.add(categoria)
                categorias.append(categoria)

    if "_default" in spec["pesos_condicionais"]:
        for categoria in spec["pesos_condicionais"]["_default"].keys():
            if categoria not in vistos:
                vistos.add(categoria)
                categorias.append(categoria)

    return categorias


def calcular_marginais_esperadas(config: dict) -> dict[str, dict[str, float]]:
    variaveis = config["amostragem"]["variaveis"]
    ordem = config["amostragem"]["dag_ordem"]
    marginais: dict[str, dict[str, float]] = {}

    for variavel in ordem:
        spec = variaveis[variavel]
        if spec.get("depende_de") is None:
            marginais[variavel] = _normalizar_pesos(spec["pesos"])
            continue

        pai = spec["depende_de"]
        pesos_marginais: defaultdict[str, float] = defaultdict(float)
        dominio_pai = marginais[pai]
        for valor_pai, probabilidade_pai in dominio_pai.items():
            linha = spec["pesos_condicionais"].get(valor_pai)
            if linha is None:
                linha = spec["pesos_condicionais"]["_default"]
            linha_normalizada = _normalizar_pesos(linha)
            for categoria, probabilidade_categoria in linha_normalizada.items():
                pesos_marginais[categoria] += probabilidade_pai * probabilidade_categoria

        categorias = _dominio_da_variavel(spec)
        marginais[variavel] = {categoria: pesos_marginais[categoria] for categoria in categorias}

    return marginais


def validar_marginal(simulacoes, variavel, pesos_esperados, alfa=0.05):
    categorias = list(pesos_esperados.keys())
    total_peso = sum(float(pesos_esperados[categoria]) for categoria in categorias)
    total = len(simulacoes)

    observado = Counter(_normalizar_observado(simulacao[variavel]) for simulacao in simulacoes)
    frequencia_observada = np.array([observado.get(categoria, 0) for categoria in categorias])
    frequencia_esperada = np.array(
        [float(pesos_esperados[categoria]) / total_peso * total for categoria in categorias]
    )

    estatistica, p_valor = chisquare(frequencia_observada, frequencia_esperada)
    return {
        "variavel": variavel,
        "chi2": round(float(estatistica), 4),
        "p_valor": round(float(p_valor), 4),
        "passou": bool(p_valor > alfa),
    }


def validar_seed_config(config: dict, alfa=0.05) -> dict:
    simulacoes = gerar_simulacoes(config)
    marginais = calcular_marginais_esperadas(config)
    resultados = [
        validar_marginal(simulacoes, variavel, pesos, alfa=alfa)
        for variavel, pesos in marginais.items()
    ]

    minimo = config["amostragem"].get("restricoes", {}).get("min_por_persona", 0)
    contagem_personas = Counter(simulacao["persona_id"] for simulacao in simulacoes)
    minimo_ok = all(contagem >= minimo for contagem in contagem_personas.values()) if minimo else True

    return {
        "seed": config["amostragem"]["seed"],
        "passou": all(resultado["passou"] for resultado in resultados) and minimo_ok,
        "resultados": resultados,
        "min_por_persona": minimo,
        "min_por_persona_passou": minimo_ok,
        "contagem_por_persona": dict(sorted(contagem_personas.items())),
    }
