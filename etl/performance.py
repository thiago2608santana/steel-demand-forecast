"""Pipeline ETL para dados de Performance Mensal do setor siderúrgico.

Fonte: arquivo manual fornecido pela equipe (dados/raw/Performance-Mensal_*.xls)
O arquivo mais recente em dados/raw/ é selecionado automaticamente via glob.
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from utils.databricks_io import salvar_tabela
from utils.transforms import validar_output

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

    Seleciona automaticamente o arquivo Performance-Mensal mais recente em
    dados/raw/ via glob. O grid cru do Excel é salvo na camada bronze e o
    resultado transformado na camada silver do Databricks.

    Args:
        cfg: Dicionário de configuração com paths.

    Returns:
        DataFrame no formato long com colunas Categoria, Especificação, Data, Valor.
    """
    path_input = _resolver_arquivo_performance(cfg)

    logger.info("Carregando Performance: %s", path_input)
    df_raw = pd.read_excel(path_input, header=None)
    salvar_tabela(df_raw.rename(columns=lambda c: f"col_{c}"), "bronze", "performance_mensal")

    df = _extrair_performance(df_raw)
    validar_output(df, "performance", min_linhas=24, colunas_obrigatorias=["Data", "Valor", "Categoria"], date_col="Data")
    salvar_tabela(df, "silver", "performance")
    logger.info("Performance concluído.")
    return df


def _resolver_arquivo_performance(cfg: dict) -> str:
    """Retorna o caminho do arquivo de performance mais recente em dados/raw/.

    O arquivo mais recente é determinado pelo nome (Performance-Mensal_YYYY.MM),
    garantindo que novos arquivos mensais sejam coletados automaticamente sem
    alterar o config.yaml.
    """
    raw_dir = Path(cfg["paths"]["anfavea_input"]).parent
    candidatos = sorted(raw_dir.glob("Performance-Mensal_*.xls*"))
    if not candidatos:
        raise FileNotFoundError(f"Nenhum arquivo Performance-Mensal_*.xls* encontrado em {raw_dir}")
    arquivo = candidatos[-1]
    logger.info("Arquivo de performance selecionado: %s", arquivo.name)
    return str(arquivo)


def _extrair_performance(df_raw: pd.DataFrame) -> pd.DataFrame:
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
    # Valores vêm do grid como object; tipar garante coluna DOUBLE na tabela Delta.
    df_melted["Valor"] = pd.to_numeric(df_melted["Valor"], errors="coerce")
    df_melted["Especificação"] = df_melted["Especificação"].astype(str).str.strip()
    df_melted = df_melted.sort_values(by=["Categoria", "Especificação", "Data"]).reset_index(drop=True)

    return df_melted
