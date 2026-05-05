"""Fixture do processo gerador original de cotas temporais.

Este arquivo preserva a lógica do script histórico
`gerar_cotas_dia_relativo_90d.txt` para que os testes de regressão não
dependam de um arquivo local fora do repositório.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from typing import Mapping


N_DIALOGOS = 6000


def maiores_restos(
    pesos: Mapping[str, float] | Mapping[int, float],
    total: int,
) -> dict:
    itens = list(pesos.items())
    soma_pesos = sum(valor for _, valor in itens)

    if soma_pesos <= 0:
        raise ValueError("A soma dos pesos deve ser positiva.")

    cotas_fracionarias = [
        (chave, total * valor / soma_pesos)
        for chave, valor in itens
    ]

    cotas = {
        chave: int(math.floor(cota))
        for chave, cota in cotas_fracionarias
    }

    unidades_restantes = total - sum(cotas.values())

    restos = sorted(
        (
            (cota - math.floor(cota), chave)
            for chave, cota in cotas_fracionarias
        ),
        reverse=True,
    )

    for _, chave in restos[:unidades_restantes]:
        cotas[chave] += 1

    return cotas


def gerar_cotas_dia_relativo_90d(
    total: int = N_DIALOGOS,
) -> tuple[OrderedDict, OrderedDict]:
    fatores_dia_semana = {
        1: 1.06,
        2: 1.10,
        3: 1.05,
        4: 1.00,
        5: 0.95,
        6: 0.76,
        7: 0.61,
    }

    fatores_semana_relativa = {
        1: 0.92,
        2: 1.00,
        3: 1.08,
        4: 0.97,
        5: 1.12,
        6: 0.95,
        7: 1.03,
        8: 0.98,
        9: 0.90,
        10: 1.15,
        11: 0.94,
        12: 0.99,
        13: 1.07,
    }

    multiplicadores_pico = {
        18: 1.22,
        47: 1.30,
        73: 1.18,
    }

    pesos_brutos = {}

    for dia in range(1, 91):
        dia_da_semana = ((dia - 1) % 7) + 1
        semana_relativa = ((dia - 1) // 7) + 1
        dia_do_mes_sintetico = ((dia - 1) % 30) + 1

        ciclo_mensal = (
            0.82
            + 0.28
            * math.exp(
                -((dia_do_mes_sintetico - 14) ** 2)
                / (2 * 3.2**2)
            )
            + 0.16
            * math.exp(
                -((dia_do_mes_sintetico - 27) ** 2)
                / (2 * 2.4**2)
            )
        )

        peso = (
            fatores_dia_semana[dia_da_semana]
            * fatores_semana_relativa[semana_relativa]
            * ciclo_mensal
            * multiplicadores_pico.get(dia, 1.0)
        )

        pesos_brutos[dia] = peso

    soma_pesos = sum(pesos_brutos.values())

    pesos_percentuais = OrderedDict(
        (
            f"d{dia:02d}",
            round(pesos_brutos[dia] / soma_pesos * 100, 4),
        )
        for dia in range(1, 91)
    )

    cotas_int = maiores_restos(
        {
            dia: pesos_brutos[dia]
            for dia in range(1, 91)
        },
        total,
    )

    cotas = OrderedDict(
        (
            f"d{dia:02d}",
            cotas_int[dia],
        )
        for dia in range(1, 91)
    )

    return pesos_percentuais, cotas
