"""Pipeline ETL para construção da tabela mestre — input do modelo de ML.

Lê todos os arquivos silver, faz merge em `Date` usando a variável alvo
(Consumo Aparente de Longos) como âncora, e persiste o resultado em dados/gold.
"""
import logging
import os

import pandas as pd

from utils.transforms import salvar_excel

logger = logging.getLogger(__name__)

_CATEGORIA_ALVO = "Consumo Aparente / Apparent Consumption (***)"
_ESPECIFICACAO_ALVO = "Longos / Long Products\n(Inclui Blocos e Tarugos / Included Ingots, Blooms and Billets)"

# Arquivos silver excluídos do merge de features (descartados na análise)
_ARQUIVOS_EXCLUIR = {"performance.xlsx", "ipea_fbc.xlsx", "bc_sgs_projecao_selic.xlsx"}


def processar_tabela_mestre(cfg: dict) -> pd.DataFrame:
    """Constrói a tabela mestre unindo variável alvo e features silver.

    Args:
        cfg: Dicionário de configuração com paths.

    Returns:
        DataFrame com variável alvo + todas as features, salvo em dados/gold.
    """
    silver_dir = cfg["paths"]["silver_dir"]
    output_path = cfg["paths"]["tabela_mestre_output"]

    df_alvo = _extrair_variavel_alvo(cfg["paths"]["performance_output"])
    df_final = _merge_features(df_alvo, silver_dir)

    salvar_excel(df_final, output_path)
    logger.info("Tabela mestre concluída: %s features, %s observações.", df_final.shape[1] - 1, df_final.shape[0])
    return df_final


def _extrair_variavel_alvo(performance_path: str) -> pd.DataFrame:
    """Lê o arquivo de performance e extrai o Consumo Aparente de Longos."""
    df = pd.read_excel(performance_path, engine="openpyxl")
    df_alvo = df[
        (df["Categoria"] == _CATEGORIA_ALVO) &
        (df["Especificação"] == _ESPECIFICACAO_ALVO)
    ].copy()
    df_alvo.reset_index(drop=True, inplace=True)
    df_alvo.rename(columns={"Valor": "Consumo Aparente", "Data": "Date"}, inplace=True)
    df_alvo.drop(["Categoria", "Especificação"], axis=1, inplace=True)
    logger.info("Variável alvo extraída: %d observações.", len(df_alvo))
    return df_alvo


def _merge_features(df_alvo: pd.DataFrame, silver_dir: str) -> pd.DataFrame:
    """Faz merge de todos os arquivos silver elegíveis sobre a variável alvo."""
    arquivos = sorted(f for f in os.listdir(silver_dir) if f.endswith(".xlsx") and f not in _ARQUIVOS_EXCLUIR)

    df = df_alvo.copy()
    for arquivo in arquivos:
        path = os.path.join(silver_dir, arquivo)
        df_temp = pd.read_excel(path, engine="openpyxl")
        df = df.merge(df_temp, on="Date")
        logger.info("Merged: %s  → shape %s", arquivo, df.shape)

    return df
