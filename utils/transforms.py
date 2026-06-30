"""Funções utilitárias de limpeza e transformação de dados."""
import datetime
import logging
from pathlib import Path
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
    """Converte strings de valores ausentes do SIDRA ('-', '...') para NaN;
    caso contrário converte para float."""
    if valor in ("-", "..."):
        return float("nan")
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
    """Salva DataFrame em Excel, criando diretórios intermediários se necessário."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False, engine="openpyxl")
    logger.info("Salvo: %s  (%d linhas, %d colunas)", path, len(df), len(df.columns))


def validar_output(
    df: pd.DataFrame,
    nome: str,
    min_linhas: int = 12,
    colunas_obrigatorias: Optional[list] = None,
    date_col: str = "Date",
    meses_recentes: int = 6,
) -> None:
    """Valida o DataFrame de output de um pipeline antes de persistir.

    Lança ValueError se alguma condição crítica falhar, impedindo que arquivos
    corrompidos ou incompletos sejam salvos em silver/gold.

    Args:
        df: DataFrame a validar.
        nome: Nome do pipeline (usado nas mensagens de erro).
        min_linhas: Número mínimo aceitável de linhas.
        colunas_obrigatorias: Colunas que devem estar presentes.
        date_col: Nome da coluna de data para checar atualidade.
        meses_recentes: Quantos meses atrás a data máxima pode estar no máximo.
    """
    erros = []

    if len(df) < min_linhas:
        erros.append(f"apenas {len(df)} linhas (mínimo esperado: {min_linhas})")

    for col in (colunas_obrigatorias or []):
        if col not in df.columns:
            erros.append(f"coluna obrigatória ausente: '{col}'")
        elif df[col].isna().all():
            erros.append(f"coluna '{col}' está completamente nula")

    if date_col in df.columns:
        data_max = pd.to_datetime(df[date_col]).max()
        limite = pd.Timestamp.now() - pd.DateOffset(months=meses_recentes)
        if data_max < limite:
            erros.append(f"data máxima ({data_max.date()}) está há mais de {meses_recentes} meses no passado")

    if erros:
        raise ValueError(f"[{nome}] Validação falhou: {'; '.join(erros)}")

    logger.info("[%s] Validação OK — %d linhas, %d colunas.", nome, len(df), len(df.columns))
