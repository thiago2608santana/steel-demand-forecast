"""Pipeline ETL para dados do Cadastro Nacional de Obras (CNO).

Fonte: https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-de-obras-cno
"""
import logging

import pandas as pd

from utils.transforms import fill_missing, filter_by_date, salvar_excel, validar_output

logger = logging.getLogger(__name__)


def processar_cno(cfg: dict) -> pd.DataFrame:
    """Extrai, transforma e salva os dados mensais de área construída do CNO.

    Lê o CSV do CNO, filtra registros do Brasil (excluindo área exterior),
    agrega a área total por mês e unidade de medida, e persiste em dados/silver.

    Args:
        cfg: Dicionário de configuração.

    Returns:
        DataFrame com série temporal mensal de área construída por unidade.
    """
    path_input = cfg["paths"]["cno_input"]
    path_output = cfg["paths"]["cno_output"]
    encoding = cfg["cno"]["encoding"]
    colunas = cfg["cno"]["colunas"]
    pais_filtro = cfg["cno"]["pais_filtro"]
    estado_excluir = cfg["cno"]["estado_excluir"]
    date_start = cfg["filters"]["date_start"]

    logger.info("Carregando CNO: %s", path_input)
    df = pd.read_csv(path_input, encoding=encoding)

    df = _selecionar_e_filtrar(df, colunas, pais_filtro, estado_excluir)
    df_pivot = _agregar_mensalmente(df)
    df_pivot = filter_by_date(df_pivot, "Date", date_start)
    fill_missing(df_pivot)

    validar_output(df_pivot, "cno", min_linhas=24, colunas_obrigatorias=["Date", "m2"], date_col="Date")
    salvar_excel(df_pivot, path_output)
    logger.info("CNO concluído.")
    return df_pivot


def _selecionar_e_filtrar(
    df: pd.DataFrame,
    colunas: list,
    pais_filtro: str,
    estado_excluir: str,
) -> pd.DataFrame:
    """Seleciona colunas relevantes e aplica filtros geográficos."""
    colunas_existentes = [c for c in colunas if c in df.columns]
    ausentes = set(colunas) - set(colunas_existentes)
    if ausentes:
        logger.warning("Colunas ausentes no CSV do CNO: %s", ausentes)

    df = df[colunas_existentes].copy()
    df = df[df["Nome do pais"] == pais_filtro].copy()
    df = df[df["Estado"] != estado_excluir].copy()
    df.drop("Nome do pais", axis=1, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["Data de início"] = pd.to_datetime(df["Data de início"])
    return df


def _agregar_mensalmente(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega a área total por mês e unidade de medida via pivot table."""
    df_pivot = df.pivot_table(
        index=pd.Grouper(key="Data de início", freq="MS"),
        columns="Unidade de medida",
        values="Área total",
        aggfunc="sum",
    ).reset_index()
    df_pivot.columns.name = None
    df_pivot.rename(columns={"Data de início": "Date"}, inplace=True)
    return df_pivot
