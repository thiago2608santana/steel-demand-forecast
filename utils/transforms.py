"""Funções utilitárias de limpeza e transformação de dados."""
import datetime
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def filter_by_date(
    df: pd.DataFrame,
    col: str,
    start: str,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Filtra o DataFrame mantendo linhas em que `col` é posterior a `start`
    e, opcionalmente, anterior a `end`."""
    mask = df[col] > pd.Timestamp(start)
    if end:
        mask &= df[col] < pd.Timestamp(end)
    return df[mask].copy().reset_index(drop=True)


def fill_missing(df: pd.DataFrame, fill_value=0) -> pd.DataFrame:
    """Preenche valores NaN com `fill_value` (in-place)."""
    df.fillna(fill_value, inplace=True)
    return df


def ajustar_valores(valor) -> float:
    """Converte strings de valores ausentes do SIDRA ('-', '...') para 0;
    caso contrário converte para float."""
    if valor in ("-", "..."):
        return 0.0
    return float(valor)


def converter_data_sidra(series: pd.Series, fmt: str = "%Y%m") -> pd.Series:
    """Converte coluna de códigos de data do SIDRA (ex: '202301') para datetime."""
    return series.apply(lambda x: datetime.datetime.strptime(x, fmt))


def clean_sidra_response(df: pd.DataFrame) -> pd.DataFrame:
    """Trata o retorno bruto da API SIDRA.

    A API retorna um DataFrame onde a primeira linha contém os nomes
    legíveis das colunas. Esta função usa essa linha como cabeçalho e a
    descarta, retornando um DataFrame limpo com índice resetado.
    """
    df = df.copy()
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)
    return df


def drop_sidra_cols(df: pd.DataFrame, extra_cols: Optional[list] = None) -> pd.DataFrame:
    """Remove colunas padrão do SIDRA que não agregam valor analítico."""
    padrao = [
        "Mês (Código)", "Mês",
        "Nível Territorial (Código)", "Nível Territorial",
        "Unidade de Medida (Código)", "Unidade de Medida",
    ]
    cols_to_drop = [c for c in (padrao + (extra_cols or [])) if c in df.columns]
    df.drop(cols_to_drop, axis=1, inplace=True)
    return df


def pivot_mensal(
    df: pd.DataFrame,
    date_col: str,
    columns_col: str,
    values_col: str,
    aggfunc: str = "sum",
) -> pd.DataFrame:
    """Cria pivot table mensal agrupado por `date_col` (freq='MS')."""
    result = df.pivot_table(
        index=[pd.Grouper(key=date_col, freq="MS")],
        columns=columns_col,
        values=values_col,
        aggfunc=aggfunc,
    ).reset_index()
    result.columns.name = None
    result.rename(columns={date_col: "Date"}, inplace=True)
    return result


def salvar_excel(df: pd.DataFrame, path: str) -> None:
    """Salva DataFrame em Excel e registra no log."""
    df.to_excel(path, index=False, engine="openpyxl")
    logger.info("Salvo: %s  (%d linhas, %d colunas)", path, len(df), len(df.columns))
