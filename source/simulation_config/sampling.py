"""Geração de simulações compatíveis com o schema v3.0."""

from __future__ import annotations

from collections import Counter

import numpy as np


def amostrar_categorica(pesos: dict, rng: np.random.Generator) -> str:
    if not pesos:
        raise ValueError("Os pesos da variável não podem ser vazios.")

    categorias = list(pesos.keys())
    valores = np.array([pesos[categoria] for categoria in categorias], dtype=float)

    if np.any(valores <= 0):
        raise ValueError("Todos os pesos devem ser positivos.")

    probabilidades = valores / float(valores.sum())
    return str(rng.choice(categorias, p=probabilidades))


def obter_pesos(spec: dict, instancia: dict) -> dict:
    pai = spec.get("depende_de")
    if pai is None:
        return spec["pesos"]

    if pai not in instancia:
        raise KeyError(f"Variável pai '{pai}' ainda não foi amostrada.")

    valor_pai = instancia[pai]
    if isinstance(valor_pai, bool):
        valor_pai = str(valor_pai).lower()

    condicionais = spec["pesos_condicionais"]
    if valor_pai in condicionais:
        return condicionais[valor_pai]

    if "_default" not in condicionais:
        raise KeyError(
            f"Não há pesos explícitos nem fallback _default para o valor '{valor_pai}'."
        )

    return condicionais["_default"]


def montar_prompt(persona: dict, template: str) -> str:
    return template.format(
        identidade=persona["identidade"],
        como_agir=persona["como_agir"],
        missao=persona["missao"],
    )


def gerar_simulacoes(config: dict) -> list[dict]:
    amostragem = config["amostragem"]
    rng = np.random.default_rng(amostragem["seed"])
    ordem = amostragem["dag_ordem"]
    variaveis = amostragem["variaveis"]
    total = amostragem["n"]

    simulacoes = []
    for indice in range(total):
        instancia = {"id": indice + 1}
        for variavel in ordem:
            spec = variaveis[variavel]
            pesos = obter_pesos(spec, instancia)
            valor = amostrar_categorica(pesos, rng)
            if spec["tipo"] == "bernoulli":
                valor = valor == "true"
            instancia[variavel] = valor
        simulacoes.append(instancia)

    minimo = amostragem.get("restricoes", {}).get("min_por_persona", 0)
    if minimo > 0:
        simulacoes = _garantir_minimo(simulacoes, variaveis, ordem, rng, minimo)

    return simulacoes


def _garantir_minimo(
    simulacoes: list[dict],
    variaveis: dict,
    ordem: list[str],
    rng: np.random.Generator,
    minimo: int,
) -> list[dict]:
    personas_todas = list(variaveis["persona_id"]["pesos"].keys())
    contagem = Counter(simulacao["persona_id"] for simulacao in simulacoes)

    for persona_id in personas_todas:
        while contagem.get(persona_id, 0) < minimo:
            mais_frequente = contagem.most_common(1)[0][0]
            indice = next(
                i
                for i, simulacao in enumerate(simulacoes)
                if simulacao["persona_id"] == mais_frequente
            )

            nova = {"id": simulacoes[indice]["id"], "persona_id": persona_id}
            for variavel in ordem[1:]:
                spec = variaveis[variavel]
                pesos = obter_pesos(spec, nova)
                valor = amostrar_categorica(pesos, rng)
                if spec["tipo"] == "bernoulli":
                    valor = valor == "true"
                nova[variavel] = valor

            simulacoes[indice] = nova
            contagem[mais_frequente] -= 1
            contagem[persona_id] = contagem.get(persona_id, 0) + 1

    return simulacoes


def exportar_formato_legado(config: dict, simulacoes: list[dict]) -> dict[str, dict]:
    template = config["template_prompt"]
    personas = config["personas"]
    legado: dict[str, dict] = {}

    for simulacao in simulacoes:
        persona = personas[simulacao["persona_id"]]
        prompt = montar_prompt(persona, template)
        legado[str(simulacao["id"])] = {
            "persona": prompt,
            "duração": simulacao["duracao"],
            "offset": simulacao["offset"],
            "weekend": simulacao["weekend"],
        }

    return legado
