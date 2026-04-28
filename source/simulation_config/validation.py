"""Validação estrutural e semântica do schema v4.2."""

from __future__ import annotations

import json
import string
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from jsonschema import Draft202012Validator

from source.simulation_config.errors import ConfigValidationError
from source.simulation_config.sampling import (
    calcular_plano_de_cotas,
    derivar_weekend,
    normalizar_valor_condicional,
    obter_pesos_condicionados,
)

EXPECTED_VERSION = "4.2"
EXPECTED_CONTEXT = "cartao_de_credito"
EXPECTED_CHANNEL = "chatbot textual em app/site"
EXPECTED_METHOD = "cotas_controladas_com_maiores_restos"
EXPECTED_FORMULA_CONJUNTA = (
    "P(dia_relativo) × P(persona) × P(offset | persona, weekend(dia_relativo)) × "
    "P(ritmo | persona) × P(missao | persona, compatibilidade ∈ {H,M})"
)
EXPECTED_PERSONA_FORMULA = "peso_final = 0.5 * prevalencia_operacional + 0.5 * cobertura_experimental"
EXPECTED_MISSION_FORMULA = (
    "peso_final_base = 0.5 * prevalencia_operacional + 0.5 * cobertura_experimental"
)
EXPECTED_WEEKEND_RULE = (
    "weekend = true quando dia_da_semana ∈ {sabado, domingo}; caso contrário, false."
)
EXPECTED_OFFSET_CATEGORIES = [
    "madrugada",
    "manha",
    "tarde",
    "noite_inicial",
    "noite_tardia",
]
EXPECTED_RHYTHM_CATEGORIES = ["rapido", "medio", "lento"]
EXPECTED_DAY_SEQUENCE = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
WEIGHT_FORMULA_TOLERANCE = Decimal("0.0001")
EXPECTED_WEEKEND_BY_DAY = {
    "segunda": False,
    "terca": False,
    "quarta": False,
    "quinta": False,
    "sexta": False,
    "sabado": True,
    "domingo": True,
}


def _load_schema() -> dict:
    schema_path = Path(__file__).with_name("schema_v4_2.json")
    with schema_path.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _validar_template_prompt(template_prompt: str) -> None:
    formatter = string.Formatter()
    campos = {
        campo
        for _, campo, _, _ in formatter.parse(template_prompt)
        if campo is not None
    }
    esperados = {"identidade", "como_agir", "missao"}
    if campos != esperados:
        raise ConfigValidationError(
            "template_prompt deve conter exatamente os placeholders "
            "{identidade}, {como_agir} e {missao}."
        )


def _validar_linha_pesos(nome: str, pesos: dict) -> None:
    if not pesos:
        raise ConfigValidationError(f"A linha de pesos '{nome}' não pode ser vazia.")
    for chave, valor in pesos.items():
        if isinstance(valor, bool) or float(valor) <= 0:
            raise ConfigValidationError(
                f"Todos os pesos de '{nome}' devem ser positivos. Chave inválida: '{chave}'."
            )


def _decimal(valor: object) -> Decimal:
    return Decimal(str(valor))


def _validar_sem_default(node: object, caminho: str = "$") -> None:
    if isinstance(node, dict):
        if "_default" in node:
            raise ConfigValidationError(f"O schema v4.2 não permite _default em {caminho}.")
        for chave, valor in node.items():
            _validar_sem_default(valor, f"{caminho}.{chave}")
    elif isinstance(node, list):
        for indice, valor in enumerate(node):
            _validar_sem_default(valor, f"{caminho}[{indice}]")


def validar_dag(config: dict) -> None:
    amostragem = config["amostragem"]
    ordem = amostragem["dag_ordem"]
    variaveis = amostragem["variaveis"]

    if len(ordem) != len(set(ordem)):
        raise ConfigValidationError("dag_ordem não pode conter variáveis duplicadas.")

    if set(ordem) != set(variaveis.keys()):
        raise ConfigValidationError("dag_ordem deve conter exatamente as variáveis definidas.")

    posicoes = {variavel: indice for indice, variavel in enumerate(ordem)}
    for variavel in ordem:
        depende_de = variaveis[variavel].get("depende_de")
        if depende_de is None:
            continue
        pais = depende_de if isinstance(depende_de, list) else [depende_de]
        for pai in pais:
            if pai not in posicoes:
                raise ConfigValidationError(
                    f"A variável '{variavel}' depende de '{pai}', que não está em dag_ordem."
                )
            if posicoes[pai] >= posicoes[variavel]:
                raise ConfigValidationError(
                    f"A dependência '{pai} -> {variavel}' cria ciclo ou viola a ordem topológica."
                )


def _validar_calendario(spec_dia: dict) -> None:
    calendario = spec_dia["calendario"]
    pesos = spec_dia["composicao_pesos"]["pesos"]

    if set(calendario.keys()) != set(pesos.keys()):
        raise ConfigValidationError(
            "Calendário e pesos de dia_relativo precisam ter o mesmo domínio."
        )

    if len(calendario) != 90:
        raise ConfigValidationError("O calendário sintético precisa conter exatamente 90 dias.")

    indices = [metadados["dia_indice"] for metadados in calendario.values()]
    if sorted(indices) != list(range(1, 91)):
        raise ConfigValidationError(
            "Calendário com dia_indice inconsistente: deve conter exatamente os índices 1..90."
        )

    for dia_relativo, metadados in calendario.items():
        dia_indice = metadados["dia_indice"]
        dia_da_semana = metadados["dia_da_semana"]
        dia_esperado = EXPECTED_DAY_SEQUENCE[(dia_indice - 1) % len(EXPECTED_DAY_SEQUENCE)]
        if dia_da_semana != dia_esperado:
            raise ConfigValidationError(
                f"Calendário com dia_indice/dia_da_semana inconsistente para '{dia_relativo}'."
            )

        weekend_esperado = EXPECTED_WEEKEND_BY_DAY.get(dia_da_semana)
        if weekend_esperado is None:
            raise ConfigValidationError(
                f"dia_da_semana inválido no calendário sintético para '{dia_relativo}'."
            )
        if bool(metadados["weekend"]) != weekend_esperado:
            raise ConfigValidationError(
                f"Calendário com weekend inconsistente para '{dia_relativo}'."
            )

    _validar_linha_pesos("dia_relativo.composicao_pesos.pesos", pesos)


def _validar_persona_id(personas: dict, spec_persona: dict) -> None:
    composicao = spec_persona["composicao_pesos"]
    if composicao["formula"] != EXPECTED_PERSONA_FORMULA:
        raise ConfigValidationError("persona_id.formula divergente do contrato esperado.")

    for chave in ("prevalencia_operacional", "cobertura_experimental", "peso_final"):
        if set(composicao[chave].keys()) != set(personas.keys()):
            raise ConfigValidationError(
                f"As chaves de persona_id.{chave} devem corresponder exatamente às personas."
            )
        _validar_linha_pesos(f"persona_id.composicao_pesos.{chave}", composicao[chave])

    for persona_id in personas.keys():
        esperado = (
            _decimal(composicao["prevalencia_operacional"][persona_id])
            + _decimal(composicao["cobertura_experimental"][persona_id])
        ) * Decimal("0.5")
        observado = _decimal(composicao["peso_final"][persona_id])
        if abs(observado - esperado) > WEIGHT_FORMULA_TOLERANCE:
            raise ConfigValidationError(
                f"persona_id.peso_final divergente da fórmula declarada para '{persona_id}'."
            )


def _validar_offset(personas: dict, spec_offset: dict) -> None:
    if spec_offset["depende_de"] != ["persona_id", "weekend"]:
        raise ConfigValidationError("offset deve depender exatamente de ['persona_id', 'weekend'].")

    categorias = list(spec_offset["categorias"].keys())
    if categorias != EXPECTED_OFFSET_CATEGORIES:
        raise ConfigValidationError("As categorias de offset não correspondem ao contrato v4.2.")

    pesos_condicionais = spec_offset["pesos_condicionais"]
    if set(pesos_condicionais.keys()) != set(personas.keys()):
        raise ConfigValidationError(
            "offset.pesos_condicionais deve cobrir exatamente todas as personas."
        )

    for persona_id, mapa_weekend in pesos_condicionais.items():
        if set(mapa_weekend.keys()) != {"false", "true"}:
            raise ConfigValidationError(
                f"offset.pesos_condicionais['{persona_id}'] deve conter apenas 'false' e 'true'."
            )
        for weekend, linha in mapa_weekend.items():
            if set(linha.keys()) != set(categorias):
                raise ConfigValidationError(
                    f"offset para persona '{persona_id}' e weekend '{weekend}' não cobre todas as categorias."
                )
            _validar_linha_pesos(f"offset.{persona_id}.{weekend}", linha)


def _validar_ritmo(personas: dict, spec_ritmo: dict) -> None:
    if spec_ritmo["depende_de"] != "persona_id":
        raise ConfigValidationError("ritmo deve depender apenas de persona_id.")

    pesos_condicionais = spec_ritmo["pesos_condicionais"]
    if set(pesos_condicionais.keys()) != set(personas.keys()):
        raise ConfigValidationError(
            "ritmo.pesos_condicionais deve cobrir exatamente todas as personas."
        )

    for persona_id, linha in pesos_condicionais.items():
        if list(linha.keys()) != EXPECTED_RHYTHM_CATEGORIES:
            raise ConfigValidationError(
                f"ritmo da persona '{persona_id}' não segue o domínio esperado."
            )
        _validar_linha_pesos(f"ritmo.{persona_id}", linha)


def _validar_missoes(personas: dict, missoes: dict, spec_missao: dict) -> None:
    if spec_missao["depende_de"] != "persona_id":
        raise ConfigValidationError("missao_id deve depender apenas de persona_id.")
    if spec_missao["compatibilidade_utilizada"] != ["H", "M"]:
        raise ConfigValidationError("missao_id deve usar compatibilidade H e M.")
    if spec_missao["compatibilidade_excluida"] != ["L", "N"]:
        raise ConfigValidationError("missao_id deve excluir compatibilidades L e N.")
    if spec_missao["pesos_por_nivel"] != {"H": 2, "M": 1}:
        raise ConfigValidationError("pesos_por_nivel deve ser exatamente {'H': 2, 'M': 1}.")

    base = spec_missao["composicao_pesos_base"]
    if base["formula"] != EXPECTED_MISSION_FORMULA:
        raise ConfigValidationError("missao_id.formula divergente do contrato esperado.")

    for chave in ("prevalencia_operacional", "cobertura_experimental", "peso_final_base"):
        if set(base[chave].keys()) != set(missoes.keys()):
            raise ConfigValidationError(
                f"missao_id.{chave} deve corresponder exatamente às missões cadastradas."
            )
        _validar_linha_pesos(f"missao_id.{chave}", base[chave])

    elegiveis = spec_missao["missoes_elegiveis_por_persona"]
    pesos_condicionais = spec_missao["pesos_condicionais"]
    if set(elegiveis.keys()) != set(personas.keys()):
        raise ConfigValidationError(
            "missoes_elegiveis_por_persona deve cobrir exatamente todas as personas."
        )
    if set(pesos_condicionais.keys()) != set(personas.keys()):
        raise ConfigValidationError(
            "missao_id.pesos_condicionais deve cobrir exatamente todas as personas."
        )

    referencias_missoes = set()
    for persona_id in personas.keys():
        niveis = elegiveis[persona_id]
        if set(niveis.keys()) != {"H", "M"}:
            raise ConfigValidationError(
                f"A persona '{persona_id}' precisa declarar compatibilidades H e M."
            )
        elegiveis_persona = list(niveis["H"]) + list(niveis["M"])
        if not elegiveis_persona:
            raise ConfigValidationError(
                f"A persona '{persona_id}' não possui nenhuma missão elegível."
            )
        if len(elegiveis_persona) != len(set(elegiveis_persona)):
            raise ConfigValidationError(
                f"A persona '{persona_id}' possui missões duplicadas na matriz de compatibilidade."
            )
        faltantes = [missao_id for missao_id in elegiveis_persona if missao_id not in missoes]
        if faltantes:
            raise ConfigValidationError(
                f"A persona '{persona_id}' referencia missões inexistentes: {faltantes}."
            )

        pesos_persona = pesos_condicionais[persona_id]
        if set(pesos_persona.keys()) != set(elegiveis_persona):
            raise ConfigValidationError(
                f"Os pesos condicionais de '{persona_id}' devem cobrir exatamente as missões H/M elegíveis."
            )
        _validar_linha_pesos(f"missao_id.{persona_id}", pesos_persona)
        referencias_missoes.update(elegiveis_persona)

    faltantes_globais = set(missoes.keys()) - referencias_missoes
    if faltantes_globais:
        raise ConfigValidationError(
            "Todas as missões devem aparecer ao menos uma vez na matriz de compatibilidade. "
            f"Faltantes: {sorted(faltantes_globais)}."
        )


def validar_config_v42(config: dict) -> None:
    if not isinstance(config, dict):
        raise ConfigValidationError("A configuração deve ser um objeto JSON.")

    versao = config.get("versao")
    if versao != EXPECTED_VERSION:
        raise ConfigValidationError(
            f"Schema com versão ausente ou não suportada. Esperado '{EXPECTED_VERSION}', recebido '{versao}'."
        )

    schema = _load_schema()
    validator = Draft202012Validator(schema)
    erros = sorted(validator.iter_errors(config), key=lambda erro: list(erro.path))
    if erros:
        erro = erros[0]
        caminho = ".".join(str(parte) for parte in erro.path) or "$"
        raise ConfigValidationError(f"Configuração v4.2 inválida em {caminho}: {erro.message}")

    _validar_sem_default(config)
    _validar_template_prompt(config["template_prompt"])
    validar_dag(config)

    if config["contexto_negocio"] != EXPECTED_CONTEXT:
        raise ConfigValidationError("contexto_negocio inválido para o contrato v4.2.")
    if config["canal"] != EXPECTED_CHANNEL:
        raise ConfigValidationError("canal inválido para o contrato v4.2.")

    janela_temporal = config["janela_temporal"]
    if janela_temporal["unidade"] != "dias" or janela_temporal["duracao"] != 90:
        raise ConfigValidationError("janela_temporal deve declarar 90 dias sintéticos.")
    if not janela_temporal["calendario_sintetico"]:
        raise ConfigValidationError("janela_temporal.calendario_sintetico deve ser true.")

    amostragem = config["amostragem"]
    if isinstance(amostragem["n"], bool) or amostragem["n"] <= 0:
        raise ConfigValidationError("'n' deve ser um inteiro positivo.")
    if isinstance(amostragem["seed"], bool):
        raise ConfigValidationError("'seed' deve ser um inteiro válido.")
    if amostragem["metodo"] != EXPECTED_METHOD:
        raise ConfigValidationError(
            "O único método suportado no schema v4.2 é 'cotas_controladas_com_maiores_restos'."
        )
    if amostragem["formula_conjunta"] != EXPECTED_FORMULA_CONJUNTA:
        raise ConfigValidationError("formula_conjunta divergente do contrato esperado.")

    if amostragem["alocacao_controlada"]["embaralhamento_final"] is not True:
        raise ConfigValidationError("alocacao_controlada.embaralhamento_final deve ser true.")
    if len(amostragem["alocacao_controlada"]["etapas"]) != 8:
        raise ConfigValidationError("alocacao_controlada deve declarar exatamente 8 etapas.")
    for etapa in amostragem["alocacao_controlada"]["etapas"]:
        if "6000" in etapa:
            raise ConfigValidationError("alocacao_controlada não pode mencionar um n fixo.")

    restricoes = amostragem["restricoes"]
    if restricoes["duracao_nao_amostrada"] is not True:
        raise ConfigValidationError("restricoes.duracao_nao_amostrada deve ser true.")
    if restricoes["compatibilidade_minima_para_cruzamento"] != "M":
        raise ConfigValidationError(
            "compatibilidade_minima_para_cruzamento deve ser exatamente 'M'."
        )

    pessoas = config["personas"]
    missoes = config["missoes"]
    variaveis = amostragem["variaveis"]

    _validar_calendario(variaveis["dia_relativo"])
    _validar_persona_id(pessoas, variaveis["persona_id"])

    weekend_spec = variaveis["weekend"]
    if weekend_spec["tipo"] != "derivada" or weekend_spec["depende_de"] != "dia_relativo":
        raise ConfigValidationError("weekend deve ser uma variável derivada de dia_relativo.")
    if weekend_spec["regra"] != EXPECTED_WEEKEND_RULE:
        raise ConfigValidationError("A regra declarada para weekend não corresponde ao contrato v4.2.")

    _validar_offset(pessoas, variaveis["offset"])
    _validar_ritmo(pessoas, variaveis["ritmo"])
    _validar_missoes(pessoas, missoes, variaveis["missao_id"])

    calcular_plano_de_cotas(config)


def _contagem_completa(contagem: Counter, dominio: list[str]) -> dict[str, int]:
    return {chave: int(contagem.get(chave, 0)) for chave in dominio}


def validar_simulacoes_geradas(config: dict, simulacoes: list[dict]) -> None:
    total = config["amostragem"]["n"]
    if len(simulacoes) != total:
        raise ConfigValidationError(
            f"O gerador deve produzir exatamente {total} registros. Recebidos: {len(simulacoes)}."
        )

    campos_esperados = {"id", "dia_relativo", "persona_id", "weekend", "offset", "ritmo", "missao_id"}
    variaveis = config["amostragem"]["variaveis"]
    calendario = variaveis["dia_relativo"]["calendario"]
    missoes_elegiveis = variaveis["missao_id"]["missoes_elegiveis_por_persona"]
    plano = calcular_plano_de_cotas(config)

    dia_dominio = list(plano["dia_relativo"].keys())
    persona_dominio = list(plano["persona_id"].keys())
    offset_dominio = list(variaveis["offset"]["categorias"].keys())

    contagem_dias = Counter()
    contagem_personas = Counter()
    indices_por_persona: defaultdict[str, list[int]] = defaultdict(list)
    indices_por_persona_weekend: defaultdict[tuple[str, str], list[int]] = defaultdict(list)

    for indice, simulacao in enumerate(simulacoes, start=1):
        if set(simulacao.keys()) != campos_esperados:
            raise ConfigValidationError("Cada simulação deve conter exatamente os campos esperados do v4.2.")
        if simulacao["id"] != indice:
            raise ConfigValidationError("Os ids das simulações devem ser sequenciais após o embaralhamento.")

        dia_relativo = simulacao["dia_relativo"]
        persona_id = simulacao["persona_id"]
        missao_id = simulacao["missao_id"]

        if dia_relativo not in calendario:
            raise ConfigValidationError(f"dia_relativo inexistente nas simulações: '{dia_relativo}'.")
        if persona_id not in config["personas"]:
            raise ConfigValidationError(f"persona_id inexistente nas simulações: '{persona_id}'.")
        if missao_id not in config["missoes"]:
            raise ConfigValidationError(f"missao_id inexistente em missoes: '{missao_id}'.")

        weekend_derivado = derivar_weekend(calendario, dia_relativo)
        if bool(simulacao["weekend"]) != weekend_derivado:
            raise ConfigValidationError(
                f"Registro com weekend inconsistente para dia_relativo '{dia_relativo}'."
            )

        pesos_offset = obter_pesos_condicionados(variaveis["offset"], simulacao)
        if simulacao["offset"] not in pesos_offset:
            raise ConfigValidationError("offset fora do domínio da CPT correspondente.")

        pesos_ritmo = obter_pesos_condicionados(variaveis["ritmo"], simulacao)
        if simulacao["ritmo"] not in pesos_ritmo:
            raise ConfigValidationError("ritmo fora do domínio da CPT correspondente.")

        elegiveis = missoes_elegiveis[persona_id]
        permitidas = set(elegiveis["H"]) | set(elegiveis["M"])
        if missao_id not in permitidas:
            raise ConfigValidationError(
                f"missao_id '{missao_id}' não é elegível para a persona '{persona_id}'."
            )

        contagem_dias[dia_relativo] += 1
        contagem_personas[persona_id] += 1
        indices_por_persona[persona_id].append(indice - 1)
        indices_por_persona_weekend[
            (persona_id, normalizar_valor_condicional(simulacao["weekend"]))
        ].append(indice - 1)

    if _contagem_completa(contagem_dias, dia_dominio) != plano["dia_relativo"]:
        raise ConfigValidationError("As cotas observadas de dia_relativo divergem do plano calculado.")
    if _contagem_completa(contagem_personas, persona_dominio) != plano["persona_id"]:
        raise ConfigValidationError("As cotas observadas de persona_id divergem do plano calculado.")

    for persona_id in persona_dominio:
        indices_persona = indices_por_persona.get(persona_id, [])
        contagem_ritmo = Counter(simulacoes[indice]["ritmo"] for indice in indices_persona)
        contagem_missao = Counter(simulacoes[indice]["missao_id"] for indice in indices_persona)

        if _contagem_completa(contagem_ritmo, list(plano["ritmo"][persona_id].keys())) != plano["ritmo"][persona_id]:
            raise ConfigValidationError(
                f"As cotas observadas de ritmo divergem do esperado para '{persona_id}'."
            )

        if _contagem_completa(contagem_missao, list(plano["missao_id"][persona_id].keys())) != plano["missao_id"][persona_id]:
            raise ConfigValidationError(
                f"As cotas observadas de missao_id divergem do esperado para '{persona_id}'."
            )

        weekend_counts = {
            "false": len(indices_por_persona_weekend.get((persona_id, "false"), [])),
            "true": len(indices_por_persona_weekend.get((persona_id, "true"), [])),
        }
        if weekend_counts != plano["persona_weekend"][persona_id]:
            raise ConfigValidationError(
                f"As cotas observadas de weekend divergem do esperado para '{persona_id}'."
            )

        for weekend in ("false", "true"):
            indices_persona_weekend = indices_por_persona_weekend.get((persona_id, weekend), [])
            contagem_offset = Counter(simulacoes[indice]["offset"] for indice in indices_persona_weekend)
            if _contagem_completa(contagem_offset, offset_dominio) != plano["offset"][persona_id][weekend]:
                raise ConfigValidationError(
                    f"As cotas observadas de offset divergem do esperado para '{persona_id}'/{weekend}."
                )
