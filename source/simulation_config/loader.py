"""Loader exclusivo para o schema v4.3."""

from __future__ import annotations

import json
from pathlib import Path

from source.simulation_config.validation import validar_config_v43


def carregar_config_v43(path: str | Path) -> dict:
    arquivo = Path(path)
    with arquivo.open("r", encoding="utf-8") as fp:
        config = json.load(fp)

    validar_config_v43(config)
    return config
