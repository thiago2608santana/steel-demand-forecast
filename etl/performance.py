"""Pipeline ETL para dados de Performance Mensal do setor siderúrgico.

Fonte: arquivo manual fornecido pela equipe (Dados/raw/Performance-Mensal_*.xls)
"""
import logging

import numpy as np
import pandas as pd

from utils.transforms import salvar_excel

logger = logging.getLogger(__name__)

_MONTHS_MAP = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

_MAIN_CATEGORIES = [
    "Produção", "Vendas Internas", "Vendas Externas",
    "Exportações", "Importações", "Consumo Aparente",
]


def processar_performance(cfg: dict) -> pd.DataFrame:
    """Extrai, transforma e salva os dados de Performance Mensal.

    Lê o arquivo Excel de Performance, converte de wide para long format
    e persiste o resultado em dados/silver.

    Args:
        cfg: Dicionário de configuração com paths.

    Returns:
        DataFrame no formato long com colunas Categoria, Especificação, Data, Valor.
    """
    path_input = cfg["paths"]["performance_input"]
    path_output = cfg["paths"]["performance_output"]

    logger.info("Carregando Performance: %s", path_input)
    df = _extrair_performance(path_input)
    salvar_excel(df, path_output)
    logger.info("Performance concluído.")
    return df


def _extrair_performance(file_path: str) -> pd.DataFrame:
    df_raw = pd.read_excel(file_path, header=None)

    espec_row_idx = None
    month_row_idx = None

    for idx, row in df_raw.iterrows():
        val = str(row[0]).lower()
        if "especifica" in val and "specification" in val:
            espec_row_idx = idx
        elif "jan" in str(row[1]).lower() and month_row_idx is None:
            month_row_idx = idx

        if espec_row_idx is not None and month_row_idx is not None:
            break

    if espec_row_idx is None or month_row_idx is None:
        raise ValueError("Não foi possível encontrar o cabeçalho de Especificação e Meses no Excel.")

    years = df_raw.iloc[espec_row_idx, 1:].ffill()
    months_raw = df_raw.iloc[month_row_idx, 1:]

    date_cols = []
    valid_cols = []

    for i in range(1, len(df_raw.columns)):
        y_val = str(years[i]).strip().replace(".0", "")
        m_str = str(months_raw[i]).split("\n")[0].lower().strip()

        if y_val.isdigit() and m_str in _MONTHS_MAP:
            dt = pd.Timestamp(year=int(y_val), month=_MONTHS_MAP[m_str], day=1)
            date_cols.append(dt)
            valid_cols.append(i)

    df_data = df_raw.iloc[month_row_idx + 1:].copy()
    df_data = df_data[[0] + valid_cols]
    df_data.columns = ["Especificação"] + date_cols
    df_data = df_data.dropna(subset=["Especificação"])

    categorias = []
    current_category = "Sem Categoria"

    for _, row in df_data.iterrows():
        espec_str = str(row["Especificação"])
        for keyword in _MAIN_CATEGORIES:
            if keyword in espec_str:
                current_category = espec_str.strip()
                break
        categorias.append(current_category)

    df_data.insert(0, "Categoria", categorias)
    df_data = df_data.dropna(subset=date_cols, how="all")

    df_melted = df_data.melt(
        id_vars=["Categoria", "Especificação"],
        var_name="Data",
        value_name="Valor",
    )
    df_melted["Data"] = pd.to_datetime(df_melted["Data"])
    df_melted["Especificação"] = df_melted["Especificação"].astype(str).str.strip()
    df_melted = df_melted.sort_values(by=["Categoria", "Especificação", "Data"]).reset_index(drop=True)

    return df_melted
