"""Funções utilitárias de formatação e visualização."""


def formatar_escala(valor, pos=None) -> str:  # noqa: ANN001
    """Formata números para k (milhares), M (milhões) ou B (bilhões) nos eixos de gráficos."""
    if valor >= 1e9:
        return f"{valor * 1e-9:.1f}B"
    if valor >= 1e6:
        return f"{valor * 1e-6:.1f}M"
    if valor >= 1e3:
        return f"{valor * 1e-3:.1f}k"
    return str(int(valor))
