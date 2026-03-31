from __future__ import annotations

import argparse
from pathlib import Path

from source.simulations.migrator import migrate_legacy_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migra arquivos legados de simulações para o schema 3.0."
    )
    parser.add_argument(
        "sources",
        nargs="+",
        help="Arquivos JSON legados a migrar.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/migrated",
        help="Diretório onde os artefatos migrados serão gravados.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for source in args.sources:
        artifacts = migrate_legacy_file(source, args.output_dir)
        print(f"[OK] {source}")
        for label, path in artifacts.items():
            print(f"  - {label}: {Path(path)}")


if __name__ == "__main__":
    main()
