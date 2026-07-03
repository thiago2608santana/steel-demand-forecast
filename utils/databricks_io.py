"""Camada de persistência no Databricks (Unity Catalog) via databricks-connect.

Único ponto de contato do projeto com o Databricks. As tabelas seguem a
arquitetura medalhão: `steeldemand.bronze.*`, `steeldemand.silver.*` e
`steeldemand.gold.tabela_mestre`. Toda escrita é full refresh (overwrite),
já que os pipelines recalculam a série histórica completa a cada execução.

Pré-requisitos (uma única vez):
    - profile configurado no ~/.databrickscfg (ver `databricks.profile` no config.yaml)
    - catálogo criado no workspace: CREATE CATALOG IF NOT EXISTS steeldemand
"""
import datetime
import logging

import pandas as pd

from config import CFG

logger = logging.getLogger(__name__)

_spark = None


def get_spark():
    """Retorna a SparkSession remota (databricks-connect), memoizada por processo.

    A autenticação usa o profile do ~/.databrickscfg definido em
    `databricks.profile` no config.yaml.
    """
    global _spark
    if _spark is None:
        from databricks.connect import DatabricksSession

        profile = CFG["databricks"]["profile"]
        logger.info("Conectando ao Databricks (profile '%s')...", profile)
        builder = DatabricksSession.builder.profile(profile)
        if CFG["databricks"].get("serverless"):
            builder = builder.serverless(True)
        _spark = builder.getOrCreate()
    return _spark


def nome_completo(camada: str, tabela: str) -> str:
    """Monta o nome qualificado `catalog.schema.tabela` (ex: steeldemand.gold.tabela_mestre)."""
    return f"{CFG['databricks']['catalog']}.{camada}.{tabela}"


def salvar_tabela(df: pd.DataFrame, camada: str, tabela: str) -> None:
    """Salva o DataFrame como tabela Delta (full refresh) no Unity Catalog.

    Colunas com espaços, acentos ou quebras de linha (comuns nas camadas
    bronze/silver) são preservadas via column mapping
    (`delta.columnMapping.mode = name`). Uma coluna de auditoria
    `ingestion_ts` é adicionada com o horário da carga.
    """
    import pyarrow as pa
    from pyspark.sql.functions import current_timestamp

    spark = get_spark()
    destino = nome_completo(camada, tabela)

    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CFG['databricks']['catalog']}.{camada}")

    # Converter via pyarrow.Table: o caminho pandas→Arrow do pyspark falha com
    # "Cannot convert ChunkedArray to Array" em colunas de string grandes
    # (ex.: SIDRA com 27 UFs concatenadas).
    tabela_arrow = pa.Table.from_pandas(_preparar_para_spark(df), preserve_index=False)
    sdf = spark.createDataFrame(tabela_arrow).withColumn(
        "ingestion_ts", current_timestamp()
    )
    (
        sdf.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .option("delta.columnMapping.mode", "name")
        .saveAsTable(destino)
    )
    logger.info("Salvo: %s  (%d linhas, %d colunas)", destino, len(df), len(df.columns))


def ler_tabela(camada: str, tabela: str, ordenar_por: str | None = None) -> pd.DataFrame:
    """Lê uma tabela Delta do Unity Catalog como pandas DataFrame, sem `ingestion_ts`.

    Delta não garante ordem de linhas — passe `ordenar_por` para séries temporais.
    """
    df = get_spark().read.table(nome_completo(camada, tabela)).toPandas()
    df = df.drop(columns=["ingestion_ts"], errors="ignore")
    if ordenar_por:
        df = df.sort_values(ordenar_por).reset_index(drop=True)
    return df


def tabela_existe(camada: str, tabela: str) -> bool:
    """True se a tabela existe no Unity Catalog."""
    return get_spark().catalog.tableExists(nome_completo(camada, tabela))


def ultima_modificacao(camada: str, tabela: str) -> datetime.datetime | None:
    """Timestamp da última escrita na tabela (DESCRIBE DETAIL), ou None se não existir."""
    if not tabela_existe(camada, tabela):
        return None
    detalhe = get_spark().sql(f"DESCRIBE DETAIL {nome_completo(camada, tabela)}").collect()[0]
    return detalhe["lastModified"]


def _preparar_para_spark(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara o pandas DataFrame para a inferência de schema do Spark.

    Nomes de coluna viram string e colunas `object` (tipos mistos vindos dos
    arquivos crus) viram string, com NaN → None para gerar NULL em vez de "nan".
    """
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda v: None if pd.isna(v) else str(v))
    return df
