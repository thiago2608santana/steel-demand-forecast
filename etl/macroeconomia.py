"""Pipeline ETL para indicadores macroeconômicos brasileiros.

Fontes:
- IPEA Data (ipeadatapy): SELIC, FBC, câmbio
- Banco Central do Brasil / SGS (python-bcb): SELIC diária, IPCA, PIB, crédito
- SIDRA/IBGE (sidrapy): SINAPI, PIM-PF, IPP, PNAD
"""
import datetime
import logging
import time

import pandas as pd

from utils.databricks_io import salvar_tabela
from utils.transforms import (
    ajustar_valores,
    clean_sidra_response,
    converter_data_sidra,
    drop_sidra_cols,
    filter_by_date,
    pivot_mensal,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Orquestrador principal
# ---------------------------------------------------------------------------

def processar_macroeconomia(cfg: dict) -> None:
    """Executa todos os pipelines de indicadores macroeconômicos em sequência.

    Chama cada extrator individualmente, registrando falhas sem interromper
    os demais. Cada extrator salva a resposta crua da API na camada bronze e
    o resultado transformado na camada silver do Databricks.

    Args:
        cfg: Dicionário de configuração.
    """
    pipelines = [
        ("SELIC IPEA", extrair_selic_ipea),
        ("FBC IPEA", extrair_fbc_ipea),
        ("Câmbio IPEA", extrair_cambio_ipea),
        ("SELIC BCB", extrair_selic_bcb),
        ("IPCA/PIB BCB", extrair_ipca_pib_bcb),
        ("Crédito Indústria BCB", extrair_credito_industria_bcb),
        ("SINAPI SIDRA", extrair_sinapi_sidra),
        ("PIM-PF SIDRA", extrair_pim_pf_sidra),
        ("IPP SIDRA", extrair_ipp_sidra),
        ("PNAD SIDRA", extrair_pnad_sidra),
    ]

    for nome, func in pipelines:
        try:
            logger.info("Iniciando: %s", nome)
            func(cfg)
            logger.info("Concluído: %s", nome)
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro em '%s': %s", nome, exc, exc_info=True)


# ---------------------------------------------------------------------------
# Extratores IPEA
# ---------------------------------------------------------------------------

def extrair_selic_ipea(cfg: dict) -> pd.DataFrame:
    """Taxa SELIC anual (% a.a.) via IPEA Data."""
    import ipeadatapy as ip

    codigo = cfg["api"]["ipea"]["selic"]
    date_start = cfg["filters"]["date_start"]

    df = ip.timeseries(codigo)
    df.reset_index(inplace=True)
    salvar_tabela(df, "bronze", "ipea_selic")

    df.rename(columns={"DATE": "Date"}, inplace=True)
    df = filter_by_date(df, "Date", date_start)
    df.drop(["CODE", "RAW DATE", "DAY", "MONTH", "YEAR"], axis=1, inplace=True)
    df.fillna(0, inplace=True)
    df.rename(columns={"VALUE ((% a.a.))": "taxa_selic_aa"}, inplace=True)

    salvar_tabela(df, "silver", "ipea_selic")
    return df


def extrair_fbc_ipea(cfg: dict) -> pd.DataFrame:
    """Índice de Formação Bruta de Capital (dessaz.) via IPEA Data."""
    import ipeadatapy as ip

    codigo = cfg["api"]["ipea"]["fbc"]
    date_start = cfg["filters"]["date_start"]

    df = ip.timeseries(codigo)
    df.reset_index(inplace=True)
    salvar_tabela(df, "bronze", "ipea_fbc")

    df.rename(columns={"DATE": "Date"}, inplace=True)
    df = filter_by_date(df, "Date", date_start)
    df.drop(["CODE", "RAW DATE", "DAY", "MONTH", "YEAR"], axis=1, inplace=True)
    df.fillna(0, inplace=True)
    df.rename(columns={"VALUE (-)": "formacao_bruta_capital"}, inplace=True)

    salvar_tabela(df, "silver", "ipea_fbc")
    return df


def extrair_cambio_ipea(cfg: dict) -> pd.DataFrame:
    """Taxa de câmbio R$/US$ (média mensal) via IPEA Data."""
    import ipeadatapy as ip

    codigo = cfg["api"]["ipea"]["cambio"]
    date_start = cfg["filters"]["date_start"]

    df = ip.timeseries(codigo)
    df.reset_index(inplace=True)
    salvar_tabela(df, "bronze", "ipea_cambio")

    df.rename(columns={"DATE": "Date"}, inplace=True)
    df = filter_by_date(df, "Date", date_start)
    df.drop(["CODE", "RAW DATE", "DAY", "MONTH", "YEAR"], axis=1, inplace=True)
    df.fillna(0, inplace=True)
    df = df.groupby(pd.Grouper(key="Date", freq="MS")).mean().reset_index()
    df.rename(columns={"VALUE (R$)": "valor_cambio_reais"}, inplace=True)

    salvar_tabela(df, "silver", "ipea_cambio")
    return df


# ---------------------------------------------------------------------------
# Extratores BCB / SGS
# ---------------------------------------------------------------------------

def extrair_selic_bcb(cfg: dict) -> pd.DataFrame:
    """Taxa SELIC diária (código 432) via BCB/SGS, agregada mensalmente."""
    from bcb import sgs

    bcb_cfg = cfg["api"]["bcb"]
    ini_1 = datetime.datetime.fromisoformat(bcb_cfg["selic_periodo_1_inicio"])
    fim_1 = datetime.datetime.fromisoformat(bcb_cfg["selic_periodo_1_fim"])
    ini_2 = datetime.datetime.fromisoformat(bcb_cfg["selic_periodo_2_inicio"])

    df1 = sgs.get(codes=("SELIC", 432), start=ini_1, end=fim_1)
    df1.reset_index(inplace=True)
    df2 = sgs.get(codes=("SELIC", 432), start=ini_2)
    df2.reset_index(inplace=True)
    salvar_tabela(pd.concat([df1, df2], ignore_index=True), "bronze", "bcb_selic")

    df1_m = df1.groupby(pd.Grouper(key="Date", freq="MS")).mean().reset_index()
    df2_m = df2.groupby(pd.Grouper(key="Date", freq="MS")).mean().reset_index()
    df = pd.concat([df1_m, df2_m], ignore_index=True)

    salvar_tabela(df, "silver", "bc_sgs_projecao_selic")
    return df


def extrair_ipca_pib_bcb(cfg: dict) -> pd.DataFrame:
    """IPCA e PIB mensal via BCB/SGS."""
    from bcb import sgs

    codigos = cfg["api"]["bcb"]["codigos"]
    date_start = cfg["filters"]["date_start"]

    df = sgs.get(codes=[("IPCA", codigos["ipca"]), ("PIB_mensal", codigos["pib_mensal"])])
    df.reset_index(inplace=True)
    salvar_tabela(df, "bronze", "bcb_ipca_pib")

    df = filter_by_date(df, "Date", date_start)

    salvar_tabela(df, "silver", "bc_sgs_ipca_pib")
    return df


def extrair_credito_industria_bcb(cfg: dict) -> pd.DataFrame:
    """Operações de crédito por atividade industrial via BCB/SGS."""
    from bcb import sgs

    codigos = cfg["api"]["bcb"]["codigos"]

    df = sgs.get(codes=[
        ("operacoes_credito_industria_construcao", codigos["credito_construcao"]),
        ("operacoes_credito_industria_infraestrutura", codigos["credito_infraestrutura"]),
        ("operacoes_credito_industria_metalurgia_siderurgia", codigos["credito_metalurgia"]),
    ])
    df.reset_index(inplace=True)
    salvar_tabela(df, "bronze", "bcb_credito_industria")

    salvar_tabela(df, "silver", "bc_sgs_operacoes_credito_industria")
    return df


# ---------------------------------------------------------------------------
# Extratores SIDRA/IBGE
# ---------------------------------------------------------------------------

def _buscar_sidra_por_uf(
    table_code: str,
    ufs: list,
    period: str,
    variables: str = "all",
    classifications: dict = None,
    sleep_interval: float = 0.5,
) -> pd.DataFrame:
    """Busca dados do SIDRA por UF e retorna DataFrame consolidado e limpo.

    Itera pelos códigos de UF com uma pausa entre requisições para evitar
    bloqueio por excesso de chamadas à API do IBGE.
    """
    import sidrapy

    dataframes = []
    for uf in ufs:
        logger.debug("Baixando tabela %s, estado %s...", table_code, uf)
        kwargs = {
            "table_code": table_code,
            "territorial_level": "3",
            "ibge_territorial_code": uf,
            "period": period,
            "variables": variables,
        }
        if classifications:
            kwargs["classifications"] = classifications

        df_uf = sidrapy.get_table(**kwargs)
        dataframes.append(df_uf)
        time.sleep(sleep_interval)

    df = pd.concat(dataframes, ignore_index=True)
    return clean_sidra_response(df)


def extrair_sinapi_sidra(cfg: dict) -> pd.DataFrame:
    """Custo de projeto por m² (SINAPI) via SIDRA tabela 647."""
    sidra_cfg = cfg["api"]["sidra"]["sinapi"]
    ufs = cfg["geo"]["uf_codes"]

    logger.info("Baixando SINAPI para %d UFs (pode levar alguns minutos)...", len(ufs))
    df = _buscar_sidra_por_uf(
        table_code=sidra_cfg["table_code"],
        ufs=ufs,
        period=sidra_cfg["period"],
        classifications={str(k): v for k, v in sidra_cfg["classifications"].items()},
    )

    salvar_tabela(df, "bronze", "sidra_sinapi_m2")

    df = df[df["Mês (Código)"] != "Mês (Código)"].copy().reset_index(drop=True)
    df["Date"] = converter_data_sidra(df["Mês (Código)"])
    drop_sidra_cols(df, extra_cols=["Unidade de Medida (Código)", "Unidade de Medida"])
    df["Valor"] = df["Valor"].apply(ajustar_valores)

    df_resultado = (
        df.groupby(pd.Grouper(key="Date", freq="MS"))["Valor"]
        .sum()
        .reset_index()
        .rename(columns={"Valor": "custo_projeto_m2"})
    )

    salvar_tabela(df_resultado, "silver", "sidra_sinapi_m2")
    return df_resultado


def extrair_pim_pf_sidra(cfg: dict) -> pd.DataFrame:
    """Pesquisa Industrial Mensal (PIM-PF) via SIDRA tabela 8888."""
    sidra_cfg = cfg["api"]["sidra"]["pim_pf"]
    ufs = cfg["geo"]["uf_codes"]
    filtrar_variavel = cfg["sectors"]["pim_pf"]["variavel"]
    filtrar_secoes = cfg["sectors"]["pim_pf"]["secoes"]

    logger.info("Baixando PIM-PF para %d UFs (pode levar alguns minutos)...", len(ufs))
    df = _buscar_sidra_por_uf(
        table_code=sidra_cfg["table_code"],
        ufs=ufs,
        period=sidra_cfg["period"],
        classifications={str(k): v for k, v in sidra_cfg["classifications"].items()},
    )

    logger.info("PIM-PF extraído: %s", df.shape)
    salvar_tabela(df, "bronze", "sidra_pim_pf")

    df = df[df["Mês (Código)"] != "Mês (Código)"].copy().reset_index(drop=True)
    df["Date"] = converter_data_sidra(df["Mês (Código)"])
    drop_sidra_cols(df)
    df["Valor"] = df["Valor"].apply(ajustar_valores)

    col_secao = "Seções e atividades industriais (CNAE 2.0)"
    df_filtrado = df[
        (df["Variável"] == filtrar_variavel) & (df[col_secao].isin(filtrar_secoes))
    ].copy().reset_index(drop=True)

    df_pivot = pivot_mensal(df_filtrado, "Date", col_secao, "Valor")

    salvar_tabela(df_pivot, "silver", "sidra_pim_pf")
    return df_pivot


def extrair_ipp_sidra(cfg: dict) -> pd.DataFrame:
    """Índice de Preços ao Produtor (IPP) via SIDRA tabela 6903."""
    import sidrapy

    sidra_cfg = cfg["api"]["sidra"]["ipp"]
    filtrar_variavel = cfg["sectors"]["ipp"]["variavel"]
    filtrar_secoes = cfg["sectors"]["ipp"]["secoes"]

    logger.info("Baixando IPP (Nacional)...")
    df_raw = sidrapy.get_table(
        table_code=sidra_cfg["table_code"],
        territorial_level="1",
        ibge_territorial_code="all",
        period=sidra_cfg["period"],
        variables="all",
        classifications={str(k): v for k, v in sidra_cfg["classifications"].items()},
    )
    df = clean_sidra_response(df_raw)
    salvar_tabela(df, "bronze", "sidra_ipp")

    col_secao = "Indústria geral, indústrias extrativas e indústrias de transformação e atividades (CNAE 2.0)"
    df_filtrado = df[
        (df["Variável"] == filtrar_variavel) & (df[col_secao].isin(filtrar_secoes))
    ].copy().reset_index(drop=True)

    df_filtrado["Date"] = converter_data_sidra(df_filtrado["Mês (Código)"])
    drop_sidra_cols(df_filtrado, extra_cols=[
        "Brasil (Código)", "Brasil",
        col_secao + " (Código)",
    ])
    df_filtrado["Valor"] = df_filtrado["Valor"].apply(ajustar_valores)

    df_pivot = pivot_mensal(df_filtrado, "Date", col_secao, "Valor")

    salvar_tabela(df_pivot, "silver", "sidra_ipp")
    return df_pivot


def extrair_pnad_sidra(cfg: dict) -> pd.DataFrame:
    """Nível de ocupação (Trimestre Móvel) via SIDRA tabela 6379 (Brasil)."""
    import sidrapy

    sidra_cfg = cfg["api"]["sidra"]["pnad"]
    filtrar_variavel = cfg["sectors"]["pnad"]["variavel"]

    logger.info("Baixando PNAD (Nível Brasil)...")
    df_raw = sidrapy.get_table(
        table_code=sidra_cfg["table_code"],
        territorial_level="1",
        ibge_territorial_code="all",
        period=sidra_cfg["period"],
        variables="all",
    )
    df = clean_sidra_response(df_raw)
    salvar_tabela(df, "bronze", "sidra_pnad")

    df_filtrado = df[df["Variável"] == filtrar_variavel].copy().reset_index(drop=True)

    df_filtrado["Date"] = converter_data_sidra(df_filtrado["Trimestre Móvel (Código)"])
    df_filtrado.drop(
        [c for c in [
            "Nível Territorial (Código)", "Nível Territorial",
            "Unidade de Medida (Código)", "Unidade de Medida",
            "Brasil (Código)", "Brasil",
            "Trimestre Móvel (Código)", "Trimestre Móvel",
            "Variável (Código)",
        ] if c in df_filtrado.columns],
        axis=1,
        inplace=True,
    )
    df_filtrado["Valor"] = df_filtrado["Valor"].apply(ajustar_valores)
    df_filtrado.rename(columns={"Valor": filtrar_variavel}, inplace=True)
    df_filtrado.drop("Variável", axis=1, inplace=True)

    salvar_tabela(df_filtrado, "silver", "sidra_pnad_ocupacao")
    return df_filtrado
