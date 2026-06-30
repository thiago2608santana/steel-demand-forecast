"""Pipeline ETL para dados de produção de veículos da ANFAVEA.

Fonte: https://anfavea.com.br/site/edicoes-em-excel/
"""
import logging

import pandas as pd

from utils.transforms import filter_by_date, salvar_excel

logger = logging.getLogger(__name__)


def processar_anfavea(cfg: dict) -> pd.DataFrame:
    """Extrai, transforma e salva os dados de produção de veículos da ANFAVEA.

    Lê o arquivo Excel da ANFAVEA, renomeia as colunas usando o esquema de
    categorias x variáveis, filtra pelo intervalo de datas configurado,
    calcula a produção total e persiste o resultado em dados/silver.

    Args:
        cfg: Dicionário de configuração.

    Returns:
        DataFrame processado com colunas de produção por categoria e total.
    """
    path_input = cfg["paths"]["anfavea_input"]
    path_output = cfg["paths"]["anfavea_output"]
    skiprows = cfg["anfavea"]["skiprows"]
    categorias = cfg["anfavea"]["categorias"]
    variaveis = cfg["anfavea"]["variaveis"]
    date_start = cfg["filters"]["date_start"]
    date_end = cfg["filters"]["date_end"]

    logger.info("Carregando ANFAVEA: %s", path_input)
    df = pd.read_excel(path_input, skiprows=skiprows, engine="openpyxl")

    df = _renomear_colunas(df, categorias, variaveis)
    df = filter_by_date(df, "Date", date_start, date_end)
    df = _extrair_producao(df)

    salvar_excel(df, path_output)
    logger.info("ANFAVEA concluído.")
    return df


def _renomear_colunas(df: pd.DataFrame, categorias: list, variaveis: list) -> pd.DataFrame:
    """Renomeia as colunas do Excel da ANFAVEA para o padrão ``Categoria_Variável``.

    O Excel da ANFAVEA usa um layout de cabeçalho mesclado onde cada bloco de
    ``len(variaveis)`` colunas pertence a uma categoria. A primeira coluna é
    sempre a data (``Unnamed: 0``). A lógica percorre as colunas ciclando o
    índice da variável a cada ``len(variaveis)`` passos.
    """
    bloco_atual = None
    idx_var = 0
    novos_nomes: dict[str, str] = {}

    for nome in df.columns:
        if "Unnamed: 0" in nome:
            novos_nomes[nome] = "Date"
            continue

        if "Unnamed" not in nome:
            bloco_atual = nome

        if bloco_atual is None:
            raise ValueError("Estrutura inesperada: categoria não encontrada antes das colunas de variáveis.")

        novo_nome = f"{bloco_atual}_{variaveis[idx_var]}"
        novos_nomes[nome] = novo_nome
        idx_var = (idx_var + 1) % len(variaveis)

    df.rename(columns=novos_nomes, inplace=True)
    # A linha 0 do DataFrame contém um cabeçalho residual do Excel
    df.drop(0, axis=0, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _extrair_producao(df: pd.DataFrame) -> pd.DataFrame:
    """Seleciona colunas de produção, calcula o total e retorna o DataFrame final."""
    colunas_producao = [c for c in df.columns if "Produção" in c]

    if not colunas_producao:
        raise ValueError("Nenhuma coluna de produção encontrada após renomeação.")

    df = df[["Date"] + colunas_producao].copy()
    df["producao_total"] = df[colunas_producao].sum(axis=1)
    return df
