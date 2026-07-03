"""Pipeline ETL para construção da tabela mestre — input do modelo de ML.

Lê todas as tabelas silver do Databricks, faz merge em `Date` usando a
variável alvo (Consumo Aparente de Longos) como âncora, e persiste o
resultado em `steeldemand.gold.tabela_mestre`.
"""
import logging

import pandas as pd

from utils.databricks_io import ler_tabela, salvar_tabela, tabela_existe
from utils.transforms import padronizar_colunas_mestre, validar_output

logger = logging.getLogger(__name__)

_CATEGORIA_ALVO = "Consumo Aparente / Apparent Consumption (***)"
_ESPECIFICACAO_ALVO = "Longos / Long Products\n(Inclui Blocos e Tarugos / Included Ingots, Blooms and Billets)"


def processar_tabela_mestre(cfg: dict) -> pd.DataFrame:
    """Constrói a tabela mestre unindo variável alvo e features silver.

    Args:
        cfg: Dicionário de configuração (assinatura padrão dos pipelines).

    Returns:
        DataFrame com variável alvo + todas as features, salvo em
        steeldemand.gold.tabela_mestre.
    """
    df_alvo = _extrair_variavel_alvo()
    df_final = _merge_features(df_alvo)
    df_final = padronizar_colunas_mestre(df_final)

    validar_output(
        df_final, "tabela_mestre", min_linhas=60,
        colunas_obrigatorias=["data", "consumo_aparente"], date_col="data",
    )
    salvar_tabela(df_final, "gold", "tabela_mestre")
    logger.info("Tabela mestre concluída: %s features, %s observações.", df_final.shape[1] - 1, df_final.shape[0])
    return df_final


def _extrair_variavel_alvo() -> pd.DataFrame:
    """Lê a tabela silver de performance e extrai o Consumo Aparente de Longos."""
    df = ler_tabela("silver", "performance", ordenar_por="Data")
    df_alvo = df[
        (df["Categoria"] == _CATEGORIA_ALVO) &
        (df["Especificação"] == _ESPECIFICACAO_ALVO)
    ].copy()
    df_alvo.reset_index(drop=True, inplace=True)
    df_alvo.rename(columns={"Valor": "Consumo Aparente", "Data": "Date"}, inplace=True)
    df_alvo.drop(["Categoria", "Especificação"], axis=1, inplace=True)
    logger.info("Variável alvo extraída: %d observações.", len(df_alvo))
    return df_alvo


def _merge_features(df_alvo: pd.DataFrame) -> pd.DataFrame:
    """Faz merge das tabelas silver elegíveis sobre a variável alvo.

    A ordem é determinística e explícita para garantir reprodutibilidade.
    Tabelas existentes no schema silver mas ausentes desta lista são ignoradas
    (ex.: performance, ipea_fbc e bc_sgs_projecao_selic, descartadas na análise),
    evitando inclusão acidental de tabelas temporárias ou experimentais.
    """
    _ORDEM_MERGE = [
        "anfavea_producao_veiculos",
        "bc_sgs_ipca_pib",
        "bc_sgs_operacoes_credito_industria",
        "gov_br_cno",
        "ipea_cambio",
        "ipea_selic",
        "sidra_ipp",
        "sidra_pim_pf",
        "sidra_pnad_ocupacao",
        "sidra_sinapi_m2",
    ]

    ausentes = [t for t in _ORDEM_MERGE if not tabela_existe("silver", t)]
    if ausentes:
        raise FileNotFoundError(
            f"Tabelas silver ausentes — rode os pipelines correspondentes antes de tabela_mestre: {ausentes}"
        )

    df = df_alvo.copy()
    for tabela in _ORDEM_MERGE:
        df_temp = ler_tabela("silver", tabela)
        df = df.merge(df_temp, on="Date", how="left")
        logger.info("Merged: %s  → shape %s", tabela, df.shape)

    # Preencher NaN gerados pelo left join: forward-fill e depois backward-fill
    # para as primeiras linhas onde alguma feature começa depois do target.
    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].ffill().bfill()

    return df
