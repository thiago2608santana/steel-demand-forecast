"""Parâmetros globais do pipeline de ML — espelham a célula de parâmetros do notebook."""
from dataclasses import asdict, dataclass, field, fields


@dataclass
class ParametrosML:
    """Parâmetros configuráveis do pipeline (defaults idênticos ao notebook)."""

    # --- Dados de entrada (schema.tabela no catálogo Databricks do projeto) ---
    fonte_tabela_mestre: str = "gold.tabela_mestre"
    target_col: str = "consumo_aparente"

    # --- Diretório onde os resultados de cada execução são salvos ---
    secoes_dir: str = "./secoes/"

    # --- Divisão temporal treino / val / teste ---
    data_inicio_val: str = "2022-01-01"
    data_inicio_teste: str = "2025-01-01"

    # --- Seleção de features ---
    threshold_multicolinearidade: float = 0.90
    threshold_corr_target: float = 0.05
    usar_permutation_importance: bool = False

    # --- Feature engineering ---
    lags_consumo: list[int] = field(default_factory=lambda: [1, 2, 3])
    lags_macro: list[int] = field(default_factory=lambda: [1, 2, 3])
    cols_macro: list[str] = field(
        default_factory=lambda: ["taxa_selic_aa", "ipca", "pib_mensal"]
    )
    janelas_media_movel: list[int] = field(default_factory=lambda: [3, 6, 12])

    # --- Peso por recência (decaimento exponencial) ---
    lambda_fator: float = 0.95

    # --- XGBoost + Optuna ---
    optuna_n_trials: int = 50
    optuna_early_stopping_rounds: int = 20
    walk_forward_n_splits: int = 8
    walk_forward_test_size: int = 6

    # --- Previsão futura (recursive multi-step forecasting) ---
    n_horizons: int = 12
    janela_plot_historico: int = 36

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, dados: dict) -> "ParametrosML":
        nomes_validos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in dados.items() if k in nomes_validos})
