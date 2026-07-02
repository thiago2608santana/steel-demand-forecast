"""Salvar, listar e recarregar sessões de treino em secoes/resultados_{timestamp}/.

Cada sessão contém:
    modelo.json    — modelo XGBoost no formato nativo (estável entre versões)
    params.json    — ParametrosML + best_params do Optuna + feature_cols + metadados
    metricas.json  — R²/MSE/MAE/MAPE por split + MAPEs do walk-forward CV
    valid_data.xlsx — X + y_real + y_pred + split (mesmo formato do notebook)
    forecast.xlsx  — previsão futura (quando gerada na aba de inferência)
"""
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from xgboost import XGBRegressor

from ml import features as ml_features
from ml.forecast import ResultadoForecast
from ml.parametros import ParametrosML
from ml.treino import SPLITS, ResultadoTreino, dividir_splits
from utils.transforms import salvar_excel

logger = logging.getLogger(__name__)


def listar_sessoes(secoes_dir: str = "./secoes/") -> list[Path]:
    """Sessões salvas, da mais recente para a mais antiga (só as recarregáveis)."""
    base = Path(secoes_dir)
    if not base.exists():
        return []
    return sorted(
        (p for p in base.glob("resultados_*") if (p / "params.json").exists()),
        reverse=True,
    )


def salvar_sessao(
    resultado: ResultadoTreino, forecast: ResultadoForecast | None = None
) -> Path:
    """Grava a sessão de treino em disco e retorna o diretório criado."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path_sessao = Path(resultado.params.secoes_dir) / f"resultados_{timestamp}"
    path_sessao.mkdir(parents=True, exist_ok=True)

    resultado.modelo.save_model(path_sessao / "modelo.json")

    df = resultado.df_features
    meta = {
        "params": resultado.params.to_dict(),
        "best_params": resultado.best_params,
        "feature_cols": resultado.feature_cols,
        "data_min": str(df["data"].min().date()),
        "data_max": str(df["data"].max().date()),
        "criado_em": timestamp,
    }
    (path_sessao / "params.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    metricas = {
        "por_split": resultado.metricas.to_dict(orient="index"),
        "cv_mapes": resultado.cv_mapes,
    }
    (path_sessao / "metricas.json").write_text(
        json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    df_valid = pd.concat([
        resultado.splits.X(s).assign(
            y_real=resultado.splits.y(s).values,
            y_pred=resultado.predicoes[s],
            split=s,
        )
        for s in SPLITS
    ]).reset_index(drop=True)
    salvar_excel(df_valid, str(path_sessao / "valid_data.xlsx"))

    if forecast is not None:
        salvar_forecast(path_sessao, forecast)

    logger.info("Sessão salva em %s", path_sessao)
    return path_sessao


def salvar_forecast(path_sessao: Path, forecast: ResultadoForecast) -> Path:
    """Grava a previsão futura no diretório da sessão."""
    destino = Path(path_sessao) / "forecast.xlsx"
    salvar_excel(forecast.tabela(), str(destino))
    return destino


def carregar_sessao(path_sessao: Path) -> ResultadoTreino:
    """Recarrega uma sessão salva, reconstruindo features e predições.

    O modelo e as métricas vêm do disco; o df de features é reconstruído a partir
    da tabela mestre atual com os parâmetros e colunas salvos — necessário porque
    a previsão recursiva usa o histórico do target, não só o modelo.
    """
    path_sessao = Path(path_sessao)
    meta = json.loads((path_sessao / "params.json").read_text(encoding="utf-8"))
    params = ParametrosML.from_dict(meta["params"])
    feature_cols = meta["feature_cols"]

    modelo = XGBRegressor()
    modelo.load_model(path_sessao / "modelo.json")

    df_base = ml_features.carregar_tabela_mestre(params.path_tabela_mestre)
    df = ml_features.preparar_features_para_inferencia(df_base, params, feature_cols)
    splits = dividir_splits(df, params)
    predicoes = {s: modelo.predict(splits.X(s)) for s in SPLITS}

    metricas_meta = json.loads((path_sessao / "metricas.json").read_text(encoding="utf-8"))
    metricas = pd.DataFrame(metricas_meta["por_split"]).T.loc[SPLITS]

    logger.info("Sessão %s recarregada (%d features)", path_sessao.name, len(feature_cols))
    return ResultadoTreino(
        params=params,
        df_features=df,
        feature_cols=feature_cols,
        splits=splits,
        best_params=meta["best_params"],
        modelo=modelo,
        predicoes=predicoes,
        metricas=metricas,
        cv_mapes=metricas_meta.get("cv_mapes", []),
    )
