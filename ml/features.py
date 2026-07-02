"""Carga da tabela mestre, feature engineering e seleção de features.

Porta fiel das células de EDA/features do notebooks/pipeline_ml.ipynb.
"""
import logging

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from xgboost import XGBRegressor

from ml.parametros import ParametrosML

logger = logging.getLogger(__name__)

# Lags do target de curto prazo que nunca devem ser descartados pela permutação
FORCE_INCLUDE = ["consumo_lag_1", "consumo_lag_2", "consumo_ma3"]


def carregar_tabela_mestre(path: str) -> pd.DataFrame:
    """Lê a tabela mestre gold, garantindo 'data' como datetime ordenado."""
    df = pd.read_excel(path, engine="openpyxl")
    df["data"] = pd.to_datetime(df["data"])
    return df.sort_values("data").reset_index(drop=True)


def remover_multicolinearidade(
    df: pd.DataFrame, target_col: str, threshold: float
) -> tuple[pd.DataFrame, list[str]]:
    """Remove features com |corr| mútua acima do limiar (target preservado)."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if target_col in numeric_cols:
        numeric_cols.remove(target_col)

    corr_matrix = df[numeric_cols].corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    to_drop = [col for col in upper.columns if any(upper[col] > threshold)]

    logger.info("Multicolinearidade: %d colunas removidas: %s", len(to_drop), to_drop)
    return df.drop(columns=to_drop), to_drop


def criar_features(df: pd.DataFrame, params: ParametrosML) -> pd.DataFrame:
    """Cria lags do target/macro, médias móveis, codificação cíclica do mês e trend.

    shift antes do rolling garante que nenhuma feature usa o valor corrente
    (sem look-ahead). Linhas com NaN gerados pelos lags são descartadas.
    """
    df = df.sort_values("data").reset_index(drop=True).copy()

    for lag in params.lags_consumo:
        df[f"consumo_lag_{lag}"] = df[params.target_col].shift(lag)

    for col in params.cols_macro:
        if col in df.columns:
            for lag in params.lags_macro:
                df[f"{col}_lag_{lag}"] = df[col].shift(lag)

    for janela in params.janelas_media_movel:
        df[f"consumo_ma{janela}"] = df[params.target_col].shift(1).rolling(janela).mean()

    df["mes_sin"] = np.sin(2 * np.pi * df["data"].dt.month / 12)
    df["mes_cos"] = np.cos(2 * np.pi * df["data"].dt.month / 12)
    df["trend"] = range(len(df))

    df = df.dropna().reset_index(drop=True)
    logger.info(
        "Feature engineering: shape %s | histórico %s → %s",
        df.shape, df["data"].min().date(), df["data"].max().date(),
    )
    return df


def filtrar_por_corr_target(
    df: pd.DataFrame, params: ParametrosML
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Etapa 1 — mantém features com |corr| com o target acima do limiar.

    A correlação é computada apenas no trainval (antes de data_inicio_teste)
    para não vazar informação do período de teste.
    """
    df_tv = df[df["data"] < params.data_inicio_teste]
    feature_cols_all = [c for c in df_tv.columns if c not in ["data", params.target_col]]

    corr_abs = (
        df_tv[feature_cols_all].corrwith(df_tv[params.target_col]).abs()
        .sort_values(ascending=False)
    )
    removidas = corr_abs[corr_abs < params.threshold_corr_target].index.tolist()
    mantidas = corr_abs[corr_abs >= params.threshold_corr_target].index.tolist()

    logger.info(
        "Filtro de correlação: %d removidas, %d mantidas", len(removidas), len(mantidas)
    )
    keep_cols = ["data", params.target_col] + mantidas
    df = df[keep_cols].sort_values("data").reset_index(drop=True)
    return df, corr_abs[mantidas], removidas


def selecao_por_permutacao(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    pesos_train: np.ndarray,
) -> tuple[list[str], pd.DataFrame]:
    """Etapa 2 — permutation importance no val set (porta das células desativadas).

    Treina um XGBoost base conservador e mantém as features cuja permutação
    degrada o MAPE no val (importance_mean > 0), forçando a inclusão dos lags
    de curto prazo do target.
    """
    sel_model = XGBRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        reg_alpha=0.5, reg_lambda=1.0, random_state=0,
    )
    sel_model.fit(X_train, y_train, sample_weight=pesos_train)

    result_perm = permutation_importance(
        sel_model, X_val, y_val,
        n_repeats=50,
        scoring="neg_mean_absolute_percentage_error",
        random_state=0,
        n_jobs=-1,
    )
    perm_df = pd.DataFrame({
        "Feature": list(X_train.columns),
        "Importance_mean": result_perm.importances_mean,
        "Importance_std": result_perm.importances_std,
    }).sort_values("Importance_mean", ascending=False).reset_index(drop=True)

    selecionadas = perm_df[perm_df["Importance_mean"] > 0]["Feature"].tolist()
    forcadas = [
        f for f in FORCE_INCLUDE
        if f in X_train.columns and f not in selecionadas
    ]
    selecionadas = forcadas + selecionadas

    removidas = [f for f in X_train.columns if f not in selecionadas]
    logger.info(
        "Permutation importance: %d removidas, %d mantidas",
        len(removidas), len(selecionadas),
    )
    return selecionadas, perm_df


def preparar_features_para_inferencia(
    df: pd.DataFrame, params: ParametrosML, feature_cols: list[str]
) -> pd.DataFrame:
    """Reconstrói o df de features de uma sessão salva usando as colunas registradas.

    Aplica o mesmo feature engineering e seleciona diretamente as colunas salvas
    no params.json — não refaz a seleção estatística, que depende do dado da época.
    """
    df = criar_features(df, params)
    faltantes = [c for c in feature_cols if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"Colunas da sessão salva ausentes na tabela mestre atual: {faltantes}"
        )
    return df[["data", params.target_col] + feature_cols].reset_index(drop=True)
