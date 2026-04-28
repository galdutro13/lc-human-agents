from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from source.simulation_config import (
    carregar_config_v42,
    gerar_simulacoes,
    validar_simulacoes_geradas,
)
from tools.enxame_usuario.simulation_projection import (
    CSV_FIELDNAMES,
    resolve_simulation_projection,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exporta um CSV de prévia das simulações v4.2 sem executar o BancoBot."
    )
    parser.add_argument("--config-file", required=True, help="Arquivo JSON v4.2")
    parser.add_argument(
        "--output-csv",
        help="Arquivo CSV de saída. Padrão: <stem_do_config>_preview.csv",
    )
    parser.add_argument(
        "--delimiter",
        default=";",
        help="Delimitador do CSV. Padrão: ';'",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Encoding do CSV. Padrão: utf-8-sig",
    )
    parser.add_argument(
        "--prompt-preview-chars",
        type=int,
        default=180,
        help="Número máximo de caracteres do prompt_preview. Padrão: 180",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescreve o arquivo de saída se ele já existir.",
    )
    return parser


def resolve_output_path(config_file: str, output_csv: str | None) -> Path:
    if output_csv:
        return Path(output_csv)
    config_path = Path(config_file)
    return Path(f"{config_path.stem}_preview.csv")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    output_path = resolve_output_path(args.config_file, args.output_csv)
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
    except Exception as exc:
        print(f"ERRO: não foi possível gerar a prévia de {args.config_file}: {exc}")
        raise SystemExit(1)

    rows = [
        {
            chave: valor
            for chave, valor in resolve_simulation_projection(
                simulacao,
                config,
                prompt_preview_chars=args.prompt_preview_chars,
            ).items()
            if chave in CSV_FIELDNAMES
        }
        for simulacao in simulacoes
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding=args.encoding) as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=CSV_FIELDNAMES,
            delimiter=args.delimiter,
        )
        writer.writeheader()
        writer.writerows(rows)

    persona_counts = Counter(row["persona_id"] for row in rows)
    mission_counts = Counter(row["missao_id"] for row in rows)
    weekend_true = sum(1 for row in rows if row["weekend"])

    print(f"[INFO] Prévia salva em: {output_path}")
    print(f"[INFO] Total de instâncias exportadas: {len(rows)}")
    print(f"[INFO] Personas únicas: {len(persona_counts)}")
    print(f"[INFO] Missões únicas: {len(mission_counts)}")
    print(f"[INFO] Instâncias em weekend: {weekend_true}")


if __name__ == "__main__":
    main()
