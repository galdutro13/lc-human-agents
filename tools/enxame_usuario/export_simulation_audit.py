from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from source.simulation_config import (
    carregar_config_v42,
    gerar_relatorio_auditoria,
    gerar_simulacoes,
    validar_simulacoes_geradas,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exporta um JSON de auditoria das cotas calculadas para simulações v4.2."
    )
    parser.add_argument("--config-file", required=True, help="Arquivo JSON v4.2")
    parser.add_argument(
        "--output-json",
        help="Arquivo JSON de saída. Padrão: <stem_do_config>_audit.json",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Encoding do JSON. Padrão: utf-8",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescreve o arquivo de saída se ele já existir.",
    )
    return parser


def resolve_output_path(config_file: str, output_json: str | None) -> Path:
    if output_json:
        return Path(output_json)
    config_path = Path(config_file)
    return Path(f"{config_path.stem}_audit.json")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    output_path = resolve_output_path(args.config_file, args.output_json)
    if output_path.exists() and not args.overwrite:
        print(
            f"ERRO: arquivo de saída já existe: {output_path}. "
            "Use --overwrite para sobrescrever."
        )
        raise SystemExit(1)

    try:
        config = carregar_config_v42(args.config_file)
        simulacoes = gerar_simulacoes(config)
        validar_simulacoes_geradas(config, simulacoes)
        relatorio = gerar_relatorio_auditoria(config, simulacoes)
    except Exception as exc:
        print(f"ERRO: não foi possível gerar a auditoria de {args.config_file}: {exc}")
        raise SystemExit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding=args.encoding) as jsonfile:
        json.dump(relatorio, jsonfile, ensure_ascii=False, indent=2)
        jsonfile.write("\n")

    checks = relatorio.get("checks", {})
    aprovados = sum(1 for valor in checks.values() if valor)
    print(f"[INFO] Auditoria salva em: {output_path}")
    print(f"[INFO] Total de instâncias auditadas: {len(simulacoes)}")
    print(f"[INFO] Checks aprovados: {aprovados}/{len(checks)}")


if __name__ == "__main__":
    main()
