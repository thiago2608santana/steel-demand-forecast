"""Carga cacheada da tabela mestre (Databricks) para a UI."""
import pandas as pd
import streamlit as st

from ml.features import carregar_tabela_mestre
from utils.databricks_io import ultima_modificacao


@st.cache_data(show_spinner=False)
def _carregar(fonte: str, versao: str) -> pd.DataFrame:
    # versao (lastModified da tabela Delta) entra na chave do cache:
    # rodar o ETL invalida automaticamente
    return carregar_tabela_mestre(fonte)


def tabela_mestre_cached(fonte: str = "gold.tabela_mestre") -> pd.DataFrame:
    camada, tabela = fonte.split(".", 1)
    return _carregar(fonte, str(ultima_modificacao(camada, tabela)))
