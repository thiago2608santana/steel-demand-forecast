"""Splits temporais, otimização com Optuna, walk-forward CV, modelo final e métricas.

Porta fiel das células de modelagem XGBoost do notebooks/pipeline_ml.ipynb.
"""
import logging
from dataclasses import dataclass, field

import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBRegressor

from ml import features as ml_features
from ml.parametros import ParametrosML

logger = logging.getLogger(__name__)

SPLITS = ["train", "val", "test"]


@dataclass
class SplitsTemporais:
    """Conjuntos treino/val/teste/trainval já separados em X, y e datas."""

    feature_cols: list[str]
    target_col: str
    dfs: dict[str, pd.DataFrame]  # chaves: train, val, test, trainval

    def X(self, split: str) -> pd.DataFrame:
        return self.dfs[split][self.feature_cols]

    def y(self, split: str) -> pd.Series:
        return self.dfs[split][self.target_col]

    def datas(self, split: str) -> pd.Series:
        return self.dfs[split]["data"]


@dataclass
class ResultadoTreino:
    """Tudo que as abas de resultados e inferência precisam de um treino."""

    params: ParametrosML
    df_features: pd.DataFrame
    feature_cols: list[str]
    splits: SplitsTemporais
    best_params: dict
    modelo: XGBRegressor
    predicoes: dict[str, np.ndarray]
    metricas: pd.DataFrame
    cv_mapes: list[float]
    corr_target: pd.Series | None = None
    removidas_multicolinearidade: list[str] = field(default_factory=list)
    removidas_corr: list[str] = field(default_factory=list)

    @property
    def residuos(self) -> dict[str, np.ndarray]:
        return {
            s: self.splits.y(s).values - self.predicoes[s] for s in SPLITS
        }

    def metrica(self, split: str, nome: str) -> float:
        return float(self.metricas.loc[split, nome])


def dividir_splits(df: pd.DataFrame, params: ParametrosML) -> SplitsTemporais:
    """Divide em treino/val/teste por data, validando datas e conjuntos não vazios."""
    if params.data_inicio_val >= params.data_inicio_teste:
        raise ValueError(
            f"data_inicio_val ({params.data_inicio_val}) deve ser anterior a "
            f"data_inicio_teste ({params.data_inicio_teste})."
        )

    dfs = {
        "test": df[df["data"] >= params.data_inicio_teste],
        "val": df[(df["data"] >= params.data_inicio_val) & (df["data"] < params.data_inicio_teste)],
        "train": df[df["data"] < params.data_inicio_val],
        "trainval": df[df["data"] < params.data_inicio_teste],
    }
    dfs = {k: v.copy().reset_index(drop=True) for k, v in dfs.items()}

    vazios = [nome for nome in SPLITS if dfs[nome].empty]
    if vazios:
        raise ValueError(
            f"Conjuntos vazios com as datas escolhidas: {vazios}. "
            f"O histórico disponível vai de {df['data'].min().date()} "
            f"a {df['data'].max().date()}."
        )

    for nome in SPLITS:
        logger.info(
            "%-9s %3d obs  (%s → %s)",
            nome, len(dfs[nome]),
            dfs[nome]["data"].min().date(), dfs[nome]["data"].max().date(),
        )

    feature_cols = [c for c in df.columns if c not in ["data", params.target_col]]
    return SplitsTemporais(feature_cols=feature_cols, target_col=params.target_col, dfs=dfs)


def calcular_pesos(n: int, lambda_fator: float) -> np.ndarray:
    """Pesos por recência: obs mais recente pesa 1, decaindo exponencialmente."""
    return lambda_fator ** np.arange(n - 1, -1, -1)


def otimizar_hiperparametros(
    splits: SplitsTemporais,
    pesos_train: np.ndarray,
    params: ParametrosML,
    trial_callback=None,
) -> optuna.Study:
    """Busca de hiperparâmetros do XGBoost com early stopping no val (sem leakage).

    trial_callback(study, trial) opcional permite à UI reportar progresso sem que
    este módulo dependa de streamlit.
    """
    X_train, y_train = splits.X("train"), splits.y("train")
    X_val, y_val = splits.X("val"), splits.y("val")

    def objective(trial: optuna.Trial) -> float:
        param = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 600),
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.1, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 0.9),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 0.9),
            "min_child_weight": trial.suggest_int("min_child_weight", 3, 15),
            "gamma": trial.suggest_float("gamma", 1e-4, 5.0, log=True),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            "random_state": 0,
            "early_stopping_rounds": params.optuna_early_stopping_rounds,
        }
        model_opt = XGBRegressor(**param)
        model_opt.fit(
            X_train, y_train,
            sample_weight=pesos_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        return mean_squared_error(y_val, model_opt.predict(X_val))

    study = optuna.create_study(direction="minimize")
    callbacks = [trial_callback] if trial_callback else None
    study.optimize(objective, n_trials=params.optuna_n_trials, callbacks=callbacks)

    logger.info("Optuna: melhor MSE (val) = %.2f | %s", study.best_value, study.best_params)
    return study


def walk_forward_cv(
    splits: SplitsTemporais,
    pesos_trainval: np.ndarray,
    best_params: dict,
    params: ParametrosML,
) -> list[float]:
    """MAPE por fold em walk-forward CV sobre o trainval completo."""
    X_trainval, y_trainval = splits.X("trainval"), splits.y("trainval")
    tscv = TimeSeriesSplit(
        n_splits=params.walk_forward_n_splits,
        test_size=params.walk_forward_test_size,
    )
    cv_mapes = []
    for fold, (tr_idx, vl_idx) in enumerate(tscv.split(X_trainval)):
        m = XGBRegressor(**best_params, random_state=0)
        m.fit(
            X_trainval.iloc[tr_idx], y_trainval.iloc[tr_idx],
            sample_weight=pesos_trainval[tr_idx],
        )
        fold_mape = mean_absolute_percentage_error(
            y_trainval.iloc[vl_idx], m.predict(X_trainval.iloc[vl_idx])
        )
        cv_mapes.append(float(fold_mape))
        logger.info("Walk-forward fold %d: MAPE = %.4f", fold + 1, fold_mape)

    logger.info(
        "Walk-forward CV MAPE: %.4f ± %.4f", np.mean(cv_mapes), np.std(cv_mapes)
    )
    return cv_mapes


def treinar_final(
    splits: SplitsTemporais, pesos_trainval: np.ndarray, best_params: dict
) -> tuple[XGBRegressor, dict[str, np.ndarray]]:
    """Modelo final treinado no trainval completo, com predições por split."""
    best_model = XGBRegressor(**best_params, random_state=0)
    best_model.fit(splits.X("trainval"), splits.y("trainval"), sample_weight=pesos_trainval)
    predicoes = {s: best_model.predict(splits.X(s)) for s in SPLITS}
    return best_model, predicoes


def calcular_metricas(splits: SplitsTemporais, predicoes: dict[str, np.ndarray]) -> pd.DataFrame:
    """R², MSE, MAE e MAPE por conjunto (index: train/val/test)."""
    linhas = {}
    for s in SPLITS:
        y_true, y_pred = splits.y(s), predicoes[s]
        linhas[s] = {
            "R²": np.round(r2_score(y_true, y_pred), 4),
            "MSE": np.round(mean_squared_error(y_true, y_pred), 4),
            "MAE": np.round(mean_absolute_error(y_true, y_pred), 4),
            "MAPE": np.round(mean_absolute_percentage_error(y_true, y_pred), 4),
        }
    return pd.DataFrame(linhas).T


class PipelineML:
    """Fachada fina que encadeia as etapas do pipeline para a UI e uso programático."""

    def __init__(self, params: ParametrosML):
        self.params = params

    def preparar_dados(self) -> tuple[pd.DataFrame, dict]:
        """Carrega a tabela mestre e aplica feature engineering + filtros estatísticos."""
        p = self.params
        df = ml_features.carregar_tabela_mestre(p.path_tabela_mestre)
        df, removidas_multi = ml_features.remover_multicolinearidade(
            df, p.target_col, p.threshold_multicolinearidade
        )
        df = ml_features.criar_features(df, p)
        df, corr_target, removidas_corr = ml_features.filtrar_por_corr_target(df, p)
        info = {
            "removidas_multicolinearidade": removidas_multi,
            "removidas_corr": removidas_corr,
            "corr_target": corr_target,
        }
        return df, info

    def treinar(self, trial_callback=None) -> ResultadoTreino:
        """Executa o pipeline completo: dados → seleção → Optuna → CV → modelo final."""
        p = self.params
        df, info = self.preparar_dados()
        splits = dividir_splits(df, p)
        pesos_train = calcular_pesos(len(splits.dfs["train"]), p.lambda_fator)
        pesos_trainval = calcular_pesos(len(splits.dfs["trainval"]), p.lambda_fator)

        if p.usar_permutation_importance:
            selecionadas, _ = ml_features.selecao_por_permutacao(
                splits.X("train"), splits.y("train"),
                splits.X("val"), splits.y("val"),
                pesos_train,
            )
            df = df[["data", p.target_col] + selecionadas]
            splits = dividir_splits(df, p)

        study = otimizar_hiperparametros(splits, pesos_train, p, trial_callback)
        best_params = dict(study.best_params)
        cv_mapes = walk_forward_cv(splits, pesos_trainval, best_params, p)
        modelo, predicoes = treinar_final(splits, pesos_trainval, best_params)
        metricas = calcular_metricas(splits, predicoes)

        return ResultadoTreino(
            params=p,
            df_features=df,
            feature_cols=splits.feature_cols,
            splits=splits,
            best_params=best_params,
            modelo=modelo,
            predicoes=predicoes,
            metricas=metricas,
            cv_mapes=cv_mapes,
            corr_target=info["corr_target"],
            removidas_multicolinearidade=info["removidas_multicolinearidade"],
            removidas_corr=info["removidas_corr"],
        )

    def prever(self, resultado: ResultadoTreino, n_horizons: int | None = None):
        """Atalho para a previsão recursiva (ver ml.forecast)."""
        from ml.forecast import prever_recursivo

        return prever_recursivo(resultado, n_horizons or self.params.n_horizons)
