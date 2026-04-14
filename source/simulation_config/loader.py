"""Loader retrocompatível para schemas v1.0 e v3.0."""

from __future__ import annotations

import json
import string
from pathlib import Path

from jsonschema import Draft202012Validator

from source.simulation_config.sampling import exportar_formato_legado, gerar_simulacoes


class ConfigValidationError(ValueError):
    """Erro de validação estrutural ou semântica do schema de simulação."""


def detectar_versao(config: dict) -> str:
    if not isinstance(config, dict):
        raise ConfigValidationError("A configuração deve ser um objeto JSON.")

    versao = config.get("versao")
    if versao is None:
        return "1.0"
    if versao != "3.0":
        raise ConfigValidationError(f"Versão de schema não suportada: '{versao}'.")
    return "3.0"


def _load_schema() -> dict:
    schema_path = Path(__file__).with_name("schema_v3.json")
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


def _dominio_variavel(variavel: str, spec: dict) -> set[str]:
    if spec.get("depende_de") is None:
        return set(spec["pesos"].keys())

    dominio = set()
    for valor_pai, linha in spec["pesos_condicionais"].items():
        if valor_pai == "_default":
            continue
        dominio.update(linha.keys())
    if "_default" in spec["pesos_condicionais"]:
        dominio.update(spec["pesos_condicionais"]["_default"].keys())
    return dominio


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
        pai = variaveis[variavel].get("depende_de")
        if pai is None:
            continue
        if pai not in posicoes:
            raise ConfigValidationError(
                f"A variável '{variavel}' depende de '{pai}', que não está em dag_ordem."
            )
        if posicoes[pai] >= posicoes[variavel]:
            raise ConfigValidationError(
                f"A dependência '{pai} -> {variavel}' cria ciclo ou viola a ordem topológica."
            )


def _validar_linha_pesos(nome: str, pesos: dict) -> None:
    if not pesos:
        raise ConfigValidationError(f"A linha de pesos '{nome}' não pode ser vazia.")
    if any(valor <= 0 for valor in pesos.values()):
        raise ConfigValidationError(f"Todos os pesos de '{nome}' devem ser positivos.")


def _validar_config_v1(config: dict) -> None:
    if not isinstance(config, dict) or not config:
        raise ConfigValidationError("O arquivo legado precisa conter um objeto JSON não vazio.")

    for chave, valor in config.items():
        if not isinstance(chave, str):
            raise ConfigValidationError("As chaves do schema legado devem ser strings.")
        if isinstance(valor, str):
            continue
        if not isinstance(valor, dict):
            raise ConfigValidationError(
                f"A entrada '{chave}' do schema legado deve ser string ou objeto."
            )
        if "persona" not in valor or not isinstance(valor["persona"], str):
            raise ConfigValidationError(
                f"A entrada '{chave}' do schema legado precisa conter um campo 'persona' textual."
            )


def validar_config_v3(config: dict) -> None:
    schema = _load_schema()
    validator = Draft202012Validator(schema)
    erros = sorted(validator.iter_errors(config), key=lambda erro: list(erro.path))
    if erros:
        erro = erros[0]
        caminho = ".".join(str(parte) for parte in erro.path) or "$"
        raise ConfigValidationError(f"Configuração v3 inválida em {caminho}: {erro.message}")

    _validar_template_prompt(config["template_prompt"])
    validar_dag(config)

    amostragem = config["amostragem"]
    if isinstance(amostragem["n"], bool) or amostragem["n"] <= 0:
        raise ConfigValidationError("'n' deve ser um inteiro positivo.")
    if isinstance(amostragem["seed"], bool):
        raise ConfigValidationError("'seed' deve ser um inteiro válido.")
    if amostragem["metodo"] != "ancestral":
        raise ConfigValidationError("O único método suportado é 'ancestral'.")

    personas = config["personas"]
    variaveis = amostragem["variaveis"]
    persona_pesos = variaveis["persona_id"]["pesos"]
    if set(persona_pesos.keys()) != set(personas.keys()):
        raise ConfigValidationError(
            "As chaves de amostragem.persona_id.pesos devem corresponder exatamente às personas."
        )
    _validar_linha_pesos("persona_id", persona_pesos)

    dominios = {
        variavel: _dominio_variavel(variavel, spec)
        for variavel, spec in variaveis.items()
    }

    for nome, spec in variaveis.items():
        if spec.get("depende_de") is None:
            continue

        pai = spec["depende_de"]
        condicionais = spec["pesos_condicionais"]

        for chave_condicional, linha in condicionais.items():
            if chave_condicional == "_default":
                continue
            if pai == "persona_id" and chave_condicional not in personas:
                raise ConfigValidationError(
                    f"'{nome}' referencia persona_id órfão em pesos_condicionais: '{chave_condicional}'."
                )
            if chave_condicional not in dominios[pai]:
                raise ConfigValidationError(
                    f"'{nome}' possui chave condicional '{chave_condicional}' fora do domínio de '{pai}'."
                )
            _validar_linha_pesos(f"{nome}.{chave_condicional}", linha)

        if "_default" in condicionais:
            _validar_linha_pesos(f"{nome}._default", condicionais["_default"])
        else:
            faltantes = dominios[pai] - {chave for chave in condicionais.keys() if chave != "_default"}
            if faltantes:
                raise ConfigValidationError(
                    f"'{nome}' não cobre todos os valores de '{pai}' e não define _default. "
                    f"Faltantes: {sorted(faltantes)}."
                )


def carregar_simulacoes(path: str | Path) -> dict[str, dict]:
    arquivo = Path(path)
    with arquivo.open("r", encoding="utf-8") as fp:
        config = json.load(fp)

    versao = detectar_versao(config)
    if versao == "1.0":
        _validar_config_v1(config)
        return config

    validar_config_v3(config)
    simulacoes = gerar_simulacoes(config)
    return exportar_formato_legado(config, simulacoes)
