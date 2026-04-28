"""Geração determinística de simulações compatíveis com o schema v4.2."""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, ROUND_FLOOR
import random

from source.simulation_config.errors import ConfigValidationError


def _to_decimal(valor: object) -> Decimal:
    return Decimal(str(valor))


def normalizar_valor_condicional(valor: object) -> str:
    if isinstance(valor, bool):
        return str(valor).lower()
    return str(valor)


def alocar_maiores_restos(
    pesos: dict[str, int | float],
    n: int,
    ordem: list[str] | None = None,
) -> dict[str, int]:
    """Converte pesos positivos em cotas inteiras com soma exata `n`.

    A função implementa o método dos maiores restos: calcula a quota ideal
    de cada categoria, fixa a parte inteira via `floor` e distribui as vagas
    restantes para as maiores partes fracionárias. Empates são resolvidos pela
    ordem informada no schema, o que preserva determinismo entre execuções.

    Args:
        pesos: Mapa categoria -> peso positivo.
        n: Total de instâncias a distribuir.
        ordem: Ordem estável de desempate. Quando omitida, usa a ordem das
            chaves de `pesos`.

    Returns:
        Um dicionário categoria -> cota inteira, sempre somando exatamente `n`.

    Raises:
        ConfigValidationError: Se `n` for inválido, se os pesos estiverem
            vazios, se houver pesos não positivos ou se a soma final divergir
            de `n`.
    """
    if isinstance(n, bool) or n < 0:
        raise ConfigValidationError("'n' deve ser um inteiro não negativo para alocação de cotas.")
    if not pesos:
        raise ConfigValidationError("Os pesos para alocação de cotas não podem ser vazios.")

    ordem_efetiva = list(ordem or pesos.keys())
    faltantes = [chave for chave in ordem_efetiva if chave not in pesos]
    if faltantes:
        raise ConfigValidationError(
            f"Ordem de alocação referencia chaves ausentes nos pesos: {faltantes}."
        )

    pesos_decimais = {}
    for chave in ordem_efetiva:
        peso = _to_decimal(pesos[chave])
        if peso <= 0:
            raise ConfigValidationError(f"Todos os pesos devem ser positivos em '{chave}'.")
        pesos_decimais[chave] = peso

    if n == 0:
        return {chave: 0 for chave in ordem_efetiva}

    total = sum(pesos_decimais.values(), start=Decimal("0"))
    if total <= 0:
        raise ConfigValidationError("A soma dos pesos deve ser positiva.")

    cotas = {}
    restos: list[tuple[Decimal, int, str]] = []
    for indice, chave in enumerate(ordem_efetiva):
        quota = pesos_decimais[chave] * Decimal(n) / total
        base = int(quota.to_integral_value(rounding=ROUND_FLOOR))
        cotas[chave] = base
        restos.append((quota - Decimal(base), indice, chave))

    faltantes_cotas = n - sum(cotas.values())
    restos.sort(key=lambda item: (-item[0], item[1]))
    for _, _, chave in restos[:faltantes_cotas]:
        cotas[chave] += 1

    if sum(cotas.values()) != n:
        raise ConfigValidationError("Soma de cotas divergente após aplicar maiores restos.")

    return cotas


def obter_pesos_condicionados(spec: dict, instancia: dict) -> dict:
    """Resolve a linha de pesos condicionais aplicável a uma instância parcial.

    Suporta tanto dependência simples (`depende_de: "persona_id"`) quanto
    dependência múltipla (`depende_de: ["persona_id", "weekend"]`). Os valores
    da instância são normalizados para o formato usado nas CPTs aninhadas,
    incluindo a conversão de booleanos para `"true"` e `"false"`.

    Args:
        spec: Especificação da variável no schema, contendo `depende_de` e
            `pesos_condicionais`.
        instancia: Valores já resolvidos das variáveis pai.

    Returns:
        O dicionário de pesos correspondente ao caminho condicional resolvido.

    Raises:
        ConfigValidationError: Se faltar alguma variável pai na instância ou se
            o caminho condicional não existir na CPT.
    """
    depende_de = spec.get("depende_de")
    if depende_de is None:
        raise ConfigValidationError("A variável não define depende_de para pesos condicionais.")

    if isinstance(depende_de, str):
        depende_de = [depende_de]

    caminho = []
    for variavel in depende_de:
        if variavel not in instancia:
            raise ConfigValidationError(
                f"depende_de referencia variável inexistente na instância atual: '{variavel}'."
            )
        caminho.append(normalizar_valor_condicional(instancia[variavel]))

    atual = spec["pesos_condicionais"]
    try:
        for chave in caminho:
            atual = atual[chave]
    except KeyError as exc:
        cadeia = " -> ".join(caminho)
        raise ConfigValidationError(
            f"Não foi possível resolver a CPT para a cadeia condicional '{cadeia}'."
        ) from exc

    return atual


def montar_prompt(persona: dict, missao: dict, template: str) -> str:
    """Monta o prompt final unindo identidade da persona e texto da missão.

    No schema v4.2 a missão não está mais embutida na persona. Esta função é o
    ponto único que compõe os três placeholders esperados pelo template:
    `identidade`, `como_agir` e `missao`.
    """
    return template.format(
        identidade=persona["identidade"],
        como_agir=persona["como_agir"],
        missao=missao["missao"],
    )


def derivar_weekend(calendario: dict[str, dict], dia_relativo: str) -> bool:
    """Deriva deterministicamente o campo `weekend` a partir do calendário.

    Diferentemente das versões antigas do pipeline, `weekend` não é amostrado.
    Ele é sempre lido do calendário sintético associado ao `dia_relativo`
    escolhido para o registro.
    """
    try:
        return bool(calendario[dia_relativo]["weekend"])
    except KeyError as exc:
        raise ConfigValidationError(f"dia_relativo inexistente no calendário: '{dia_relativo}'.") from exc


def _sequencia_balanceada(cotas: dict[str, int], ordem: list[str] | None = None) -> list[str]:
    """Expande cotas inteiras em uma sequência distribuída de forma balanceada.

    Em vez de materializar cada categoria em blocos contíguos, a função faz um
    round-robin sobre as categorias com saldo restante. Isso reduz padrões
    artificiais antes do embaralhamento final e mantém o resultado
    deterministicamente reproduzível.
    """
    ordem_efetiva = [chave for chave in (ordem or list(cotas.keys())) if cotas.get(chave, 0) > 0]
    restantes = {chave: int(cotas[chave]) for chave in ordem_efetiva}
    total = sum(restantes.values())
    sequencia: list[str] = []

    while len(sequencia) < total:
        avancou = False
        for chave in ordem_efetiva:
            if restantes[chave] <= 0:
                continue
            sequencia.append(chave)
            restantes[chave] -= 1
            avancou = True
        if not avancou:
            break

    if len(sequencia) != total:
        raise ConfigValidationError("Falha ao expandir cotas em sequência balanceada.")

    return sequencia


def _ordenar_indices_por_dia(indices: list[int], simulacoes: list[dict], calendario: dict[str, dict]) -> list[int]:
    """Ordena registros de uma persona pela posição temporal no calendário."""
    return sorted(
        indices,
        key=lambda indice: (
            calendario[simulacoes[indice]["dia_relativo"]]["dia_indice"],
            indice,
        ),
    )


def _construir_registros_base(
    config: dict,
    dia_cotas: dict[str, int],
    persona_cotas: dict[str, int],
) -> list[dict]:
    """Cria a malha base de registros com dia, persona e weekend derivado.

    Esta etapa materializa apenas as variáveis marginais `dia_relativo` e
    `persona_id`. Em seguida, deriva `weekend` do calendário sintético, deixando
    `offset`, `ritmo` e `missao_id` para as etapas condicionais posteriores.
    """
    variaveis = config["amostragem"]["variaveis"]
    calendario = variaveis["dia_relativo"]["calendario"]
    dia_ordem = list(variaveis["dia_relativo"]["composicao_pesos"]["pesos"].keys())
    persona_ordem = list(variaveis["persona_id"]["composicao_pesos"]["peso_final"].keys())

    dia_sequencia = _sequencia_balanceada(dia_cotas, dia_ordem)
    persona_sequencia = _sequencia_balanceada(persona_cotas, persona_ordem)

    return [
        {
            "dia_relativo": dia_relativo,
            "persona_id": persona_id,
            "weekend": derivar_weekend(calendario, dia_relativo),
        }
        for dia_relativo, persona_id in zip(dia_sequencia, persona_sequencia, strict=True)
    ]


def _contagem_completa(contagem: Counter | dict[str, int], dominio: list[str]) -> dict[str, int]:
    """Completa contagens ausentes com zero para um domínio conhecido."""
    return {chave: int(contagem.get(chave, 0)) for chave in dominio}


def calcular_plano_de_cotas(config: dict) -> dict:
    """Calcula o plano determinístico completo de cotas para uma execução.

    Esta é a fonte única de verdade do planejamento estatístico da simulação.
    A função deriva, a partir dos pesos e do `n` configurado, as cotas
    marginais de `dia_relativo` e `persona_id` e as cotas condicionais de
    `offset`, `ritmo` e `missao_id`.

    O resultado é reutilizado pelo gerador, pela validação e pela auditoria,
    evitando duplicação de lógica e garantindo consistência entre planejamento,
    execução e conferência.

    Args:
        config: Configuração v4.2 já validada.

    Returns:
        Um dicionário com o plano completo de cotas marginais e condicionais,
        incluindo a decomposição por persona e por weekend.
    """
    amostragem = config["amostragem"]
    variaveis = amostragem["variaveis"]
    total = amostragem["n"]

    dia_pesos = variaveis["dia_relativo"]["composicao_pesos"]["pesos"]
    dia_ordem = list(dia_pesos.keys())
    dia_cotas = alocar_maiores_restos(dia_pesos, total, dia_ordem)

    persona_pesos = variaveis["persona_id"]["composicao_pesos"]["peso_final"]
    persona_ordem = list(persona_pesos.keys())
    persona_cotas = alocar_maiores_restos(persona_pesos, total, persona_ordem)

    registros_base = _construir_registros_base(config, dia_cotas, persona_cotas)
    calendario = variaveis["dia_relativo"]["calendario"]
    offset_spec = variaveis["offset"]
    offset_ordem = list(offset_spec["categorias"].keys())
    ritmo_spec = variaveis["ritmo"]
    missao_spec = variaveis["missao_id"]

    indices_por_persona: defaultdict[str, list[int]] = defaultdict(list)
    for indice, simulacao in enumerate(registros_base):
        indices_por_persona[simulacao["persona_id"]].append(indice)

    persona_weekend: dict[str, dict[str, int]] = {}
    offset_cotas: dict[str, dict[str, dict[str, int]]] = {}
    ritmo_cotas: dict[str, dict[str, int]] = {}
    missao_cotas: dict[str, dict[str, int]] = {}

    for persona_id in persona_ordem:
        indices_persona = indices_por_persona.get(persona_id, [])
        indices_ordenados = _ordenar_indices_por_dia(indices_persona, registros_base, calendario)
        indices_por_weekend: defaultdict[str, list[int]] = defaultdict(list)
        for indice in indices_ordenados:
            chave_weekend = normalizar_valor_condicional(registros_base[indice]["weekend"])
            indices_por_weekend[chave_weekend].append(indice)

        persona_weekend[persona_id] = {
            "false": len(indices_por_weekend.get("false", [])),
            "true": len(indices_por_weekend.get("true", [])),
        }

        offset_cotas[persona_id] = {}
        for chave_weekend in ("false", "true"):
            pesos_offset = obter_pesos_condicionados(
                offset_spec,
                {
                    "persona_id": persona_id,
                    "weekend": chave_weekend == "true",
                },
            )
            offset_cotas[persona_id][chave_weekend] = alocar_maiores_restos(
                pesos_offset,
                persona_weekend[persona_id][chave_weekend],
                offset_ordem,
            )

        pesos_ritmo = obter_pesos_condicionados(ritmo_spec, {"persona_id": persona_id})
        ritmo_ordem = list(pesos_ritmo.keys())
        ritmo_cotas[persona_id] = alocar_maiores_restos(
            pesos_ritmo,
            len(indices_ordenados),
            ritmo_ordem,
        )

        pesos_missao = obter_pesos_condicionados(missao_spec, {"persona_id": persona_id})
        missao_ordem = list(pesos_missao.keys())
        missao_cotas[persona_id] = alocar_maiores_restos(
            pesos_missao,
            len(indices_ordenados),
            missao_ordem,
        )

    return {
        "n": total,
        "dia_relativo": dia_cotas,
        "persona_id": persona_cotas,
        "persona_weekend": persona_weekend,
        "offset": offset_cotas,
        "ritmo": ritmo_cotas,
        "missao_id": missao_cotas,
    }


def _contagens_observadas(config: dict, simulacoes: list[dict]) -> dict:
    """Resume simulações geradas em contagens comparáveis ao plano de cotas.

    O formato retornado espelha a estrutura produzida por
    `calcular_plano_de_cotas`, o que permite comparar diretamente planejado e
    observado em auditorias e validações.
    """
    variaveis = config["amostragem"]["variaveis"]
    dia_dominio = list(variaveis["dia_relativo"]["composicao_pesos"]["pesos"].keys())
    persona_dominio = list(variaveis["persona_id"]["composicao_pesos"]["peso_final"].keys())
    offset_dominio = list(variaveis["offset"]["categorias"].keys())

    contagem_dias = Counter(simulacao["dia_relativo"] for simulacao in simulacoes)
    contagem_personas = Counter(simulacao["persona_id"] for simulacao in simulacoes)

    offset_counts: dict[str, dict[str, dict[str, int]]] = {}
    ritmo_counts: dict[str, dict[str, int]] = {}
    missao_counts: dict[str, dict[str, int]] = {}
    persona_weekend_counts: dict[str, dict[str, int]] = {}

    indices_por_persona: defaultdict[str, list[int]] = defaultdict(list)
    indices_por_persona_weekend: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
    for indice, simulacao in enumerate(simulacoes):
        persona_id = simulacao["persona_id"]
        weekend = normalizar_valor_condicional(simulacao["weekend"])
        indices_por_persona[persona_id].append(indice)
        indices_por_persona_weekend[(persona_id, weekend)].append(indice)

    for persona_id in persona_dominio:
        indices_persona = indices_por_persona.get(persona_id, [])
        pesos_ritmo = variaveis["ritmo"]["pesos_condicionais"][persona_id]
        pesos_missao = variaveis["missao_id"]["pesos_condicionais"][persona_id]
        ritmo_counts[persona_id] = _contagem_completa(
            Counter(simulacoes[indice]["ritmo"] for indice in indices_persona),
            list(pesos_ritmo.keys()),
        )
        missao_counts[persona_id] = _contagem_completa(
            Counter(simulacoes[indice]["missao_id"] for indice in indices_persona),
            list(pesos_missao.keys()),
        )

        persona_weekend_counts[persona_id] = {}
        offset_counts[persona_id] = {}
        for weekend in ("false", "true"):
            indices_slice = indices_por_persona_weekend.get((persona_id, weekend), [])
            persona_weekend_counts[persona_id][weekend] = len(indices_slice)
            offset_counts[persona_id][weekend] = _contagem_completa(
                Counter(simulacoes[indice]["offset"] for indice in indices_slice),
                offset_dominio,
            )

    return {
        "dia_relativo": _contagem_completa(contagem_dias, dia_dominio),
        "persona_id": _contagem_completa(contagem_personas, persona_dominio),
        "persona_weekend": persona_weekend_counts,
        "offset": offset_counts,
        "ritmo": ritmo_counts,
        "missao_id": missao_counts,
    }


def gerar_relatorio_auditoria(config: dict, simulacoes: list[dict] | None = None) -> dict:
    """Gera um artefato estruturado de auditoria do plano de amostragem.

    Quando recebe simulações observadas, o relatório inclui também contagens
    efetivamente produzidas e checks booleanos de conformidade entre o plano e
    a materialização final.

    Args:
        config: Configuração v4.2 já validada.
        simulacoes: Lista opcional de simulações materializadas.

    Returns:
        Um dicionário pronto para serialização em JSON com metadados da
        execução, cotas calculadas e, opcionalmente, comparações com o
        observado.
    """
    plano = calcular_plano_de_cotas(config)
    relatorio = {
        "versao_schema": config["versao"],
        "n": config["amostragem"]["n"],
        "seed": config["amostragem"]["seed"],
        "cotas_calculadas": plano,
    }

    if simulacoes is not None:
        observado = _contagens_observadas(config, simulacoes)
        relatorio["contagens_observadas"] = observado
        relatorio["checks"] = {
            "dia_relativo_confere": observado["dia_relativo"] == plano["dia_relativo"],
            "persona_id_confere": observado["persona_id"] == plano["persona_id"],
            "persona_weekend_confere": observado["persona_weekend"] == plano["persona_weekend"],
            "offset_confere": observado["offset"] == plano["offset"],
            "ritmo_confere": observado["ritmo"] == plano["ritmo"],
            "missao_id_confere": observado["missao_id"] == plano["missao_id"],
        }

    return relatorio


def gerar_simulacoes(config: dict) -> list[dict]:
    """Materializa as instâncias finais da simulação de personas.

    O fluxo é totalmente determinístico para um mesmo `config`: primeiro
    calcula-se o plano de cotas, depois constroem-se os registros base com
    `dia_relativo`, `persona_id` e `weekend`, em seguida são preenchidas as
    variáveis condicionais (`offset`, `ritmo`, `missao_id`) e, por fim, a lista
    inteira é embaralhada com a `seed` configurada.

    Args:
        config: Configuração v4.2 já validada.

    Returns:
        Lista de registros contendo `id`, `dia_relativo`, `persona_id`,
        `weekend`, `offset`, `ritmo` e `missao_id`.
    """
    amostragem = config["amostragem"]
    variaveis = amostragem["variaveis"]
    calendario = variaveis["dia_relativo"]["calendario"]
    plano = calcular_plano_de_cotas(config)

    simulacoes = _construir_registros_base(config, plano["dia_relativo"], plano["persona_id"])

    indices_por_persona: defaultdict[str, list[int]] = defaultdict(list)
    for indice, simulacao in enumerate(simulacoes):
        indices_por_persona[simulacao["persona_id"]].append(indice)

    offset_ordem = list(variaveis["offset"]["categorias"].keys())

    for persona_id, indices_persona in indices_por_persona.items():
        indices_ordenados = _ordenar_indices_por_dia(indices_persona, simulacoes, calendario)

        indices_por_weekend: defaultdict[str, list[int]] = defaultdict(list)
        for indice in indices_ordenados:
            chave_weekend = normalizar_valor_condicional(simulacoes[indice]["weekend"])
            indices_por_weekend[chave_weekend].append(indice)

        for chave_weekend in ("false", "true"):
            indices_weekend = indices_por_weekend.get(chave_weekend, [])
            cotas_offset = plano["offset"][persona_id][chave_weekend]
            sequencia_offset = _sequencia_balanceada(cotas_offset, offset_ordem)
            for indice, offset in zip(indices_weekend, sequencia_offset, strict=True):
                simulacoes[indice]["offset"] = offset

        cotas_ritmo = plano["ritmo"][persona_id]
        sequencia_ritmo = _sequencia_balanceada(cotas_ritmo, list(cotas_ritmo.keys()))
        for indice, ritmo in zip(indices_ordenados, sequencia_ritmo, strict=True):
            simulacoes[indice]["ritmo"] = ritmo

        cotas_missao = plano["missao_id"][persona_id]
        sequencia_missao = _sequencia_balanceada(cotas_missao, list(cotas_missao.keys()))
        for indice, missao_id in zip(indices_ordenados, sequencia_missao, strict=True):
            simulacoes[indice]["missao_id"] = missao_id

    rng = random.Random(amostragem["seed"])
    rng.shuffle(simulacoes)

    for indice, simulacao in enumerate(simulacoes, start=1):
        simulacao["id"] = indice

    return simulacoes
