"""CLI para migrar personas_tf.json do schema v1.0 para o schema v3.0."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from source.simulation_config import migrate_v1_to_v3, validar_config_v3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Converte o schema legado de personas para o schema v3.0."
    )
    parser.add_argument("--input", required=True, help="Arquivo JSON legado (v1.0).")
    parser.add_argument("--output", required=True, help="Arquivo de saída para o config_v3.json.")
    parser.add_argument(
        "--report-output",
        default="migration_report.json",
        help="Arquivo JSON de saída para o relatório da migração.",
    )
    parser.add_argument("--n", type=int, default=300, help="Número de simulações a gerar.")
    parser.add_argument("--seed", type=int, default=42, help="Seed inicial para a busca estatística.")
    parser.add_argument(
        "--min-por-persona",
        type=int,
        default=4,
        help="Restrição mínima por persona no schema v3.0.",
    )
    parser.add_argument(
        "--max-seed",
        type=int,
        default=10000,
        help="Última seed a considerar na busca estatística.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Nível de significância para os testes chi-quadrado.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    with input_path.open("r", encoding="utf-8") as arquivo:
        legado = json.load(arquivo)

    config_v3, relatorio = migrate_v1_to_v3(
        legado,
        source_path=str(input_path),
        n=args.n,
        seed=args.seed,
        min_por_persona=args.min_por_persona,
        search_seed=True,
        max_seed=args.max_seed,
        alfa=args.alpha,
    )
    validar_config_v3(config_v3)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(config_v3, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_path = Path(args.report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Configuração v3 escrita em: {output_path}")
    print(f"Relatório da migração escrito em: {report_path}")
    print(
        "Seed final selecionada:",
        relatorio["statistical_validation"]["seed"],
    )


if __name__ == "__main__":
    main()
