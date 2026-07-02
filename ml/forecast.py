"""Previsão recursiva multi-step com horizonte real.

Porta fiel da seção "Previsão com Horizonte Real" do notebooks/pipeline_ml.ipynb:
retreina em todo o histórico, atualiza lags/rolling do target recursivamente com as
próprias previsões e congela as features externas no último valor observado.
"""
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ml.treino import ResultadoTreino, calcular_pesos

logger = logging.getLogger(__name__)


@dataclass
class ResultadoForecast:
    """Previsão futura + contexto para o gráfico e a banda de incerteza."""

    forecast_df: pd.DataFrame  # colunas: Data, Previsao
    error_bands: np.ndarray    # ±MAE_test × sqrt(h) por horizonte
    hist: pd.Series            # série histórica completa do target (index: data)
    ultima_data: pd.Timestamp
    mae_ref: float

    def tabela(self) -> pd.DataFrame:
        """Previsão formatada com os limites da faixa de incerteza."""
        return pd.DataFrame({
            "Data": self.forecast_df["Data"].dt.strftime("%Y-%m"),
            "Previsao": self.forecast_df["Previsao"].round(1),
            "Limite_inferior": (self.forecast_df["Previsao"] - self.error_bands).round(1),
            "Limite_superior": (self.forecast_df["Previsao"] + self.error_bands).round(1),
        })


def _classificar_features(feature_cols: list[str]) -> tuple[dict, dict, list[str]]:
    """Separa as features em lags recursivos, rolling recursivos e externas fixas."""
    lag_map, roll_map, ext_cols = {}, {}, []
    for col in feature_cols:
        if col.startswith("consumo_lag_"):
            lag_map[col] = int(col.split("_")[-1])
        elif col.startswith("consumo_ma"):
            roll_map[col] = int(col.replace("consumo_ma", ""))
        elif col not in ("mes_sin", "mes_cos", "trend"):
            ext_cols.append(col)
    return lag_map, roll_map, ext_cols


def prever_recursivo(resultado: ResultadoTreino, n_horizons: int) -> ResultadoForecast:
    """Gera previsão de n_horizons meses à frente com o setup da sessão de treino."""
    params = resultado.params
    df = resultado.df_features
    feature_cols = resultado.feature_cols
    target_col = params.target_col

    lag_map, roll_map, ext_cols = _classificar_features(feature_cols)
    logger.info(
        "Forecast: lags=%s rolling=%s externas fixas=%s", lag_map, roll_map, ext_cols
    )

    # Retreino em todo o histórico disponível (inclui o período de teste)
    X_all = df[feature_cols]
    y_all = df[target_col]
    pesos_all = calcular_pesos(len(y_all), params.lambda_fator)

    best_params_deploy = {
        k: v for k, v in resultado.best_params.items() if k != "early_stopping_rounds"
    }
    model_full = XGBRegressor(**best_params_deploy, random_state=0)
    model_full.fit(X_all, y_all, sample_weight=pesos_all)
    logger.info(
        "Retreino full: %d obs (%s → %s)",
        len(y_all), df["data"].min().date(), df["data"].max().date(),
    )

    serie_hist = list(df[target_col].values)  # buffer crescente com as previsões
    ultima_data = df["data"].max()
    ultima_linha = df.iloc[-1]
    trend_base = int(df["trend"].max()) if "trend" in df.columns else 0

    previsoes_fut, datas_fut = [], []
    for h in range(1, n_horizons + 1):
        prox_data = ultima_data + pd.DateOffset(months=h)
        X_next = {}
        for col in feature_cols:
            if col in lag_map:
                X_next[col] = serie_hist[-lag_map[col]]
            elif col in roll_map:
                X_next[col] = float(np.mean(serie_hist[-roll_map[col]:]))
            elif col == "mes_sin":
                X_next[col] = np.sin(2 * np.pi * prox_data.month / 12)
            elif col == "mes_cos":
                X_next[col] = np.cos(2 * np.pi * prox_data.month / 12)
            elif col == "trend":
                X_next[col] = trend_base + h
            else:
                X_next[col] = float(ultima_linha[col])

        pred = float(model_full.predict(pd.DataFrame([X_next])[feature_cols])[0])
        serie_hist.append(pred)
        previsoes_fut.append(pred)
        datas_fut.append(prox_data)

    forecast_df = pd.DataFrame({"Data": datas_fut, "Previsao": previsoes_fut})

    # Incerteza cresce com o horizonte porque o erro se propaga nos lags (≈ random walk)
    mae_ref = resultado.metrica("test", "MAE")
    error_bands = mae_ref * np.sqrt(np.arange(1, n_horizons + 1))

    hist = df.set_index("data")[target_col].sort_index()
    return ResultadoForecast(
        forecast_df=forecast_df,
        error_bands=error_bands,
        hist=hist,
        ultima_data=ultima_data,
        mae_ref=float(mae_ref),
    )
