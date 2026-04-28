"""Tipos de erro compartilhados pelo pacote de configuração de simulação."""


class ConfigValidationError(ValueError):
    """Erro de validação estrutural ou semântica do schema de simulação."""
