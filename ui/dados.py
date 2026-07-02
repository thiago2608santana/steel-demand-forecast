"""Carga cacheada da tabela mestre para a UI."""
import os

import pandas as pd
import streamlit as st

from ml.features import carregar_tabela_mestre


@st.cache_data(show_spinner=False)
def _carregar(path: str, mtime: float) -> pd.DataFrame:
    # mtime entra na chave do cache: rodar o ETL invalida automaticamente
    return carregar_tabela_mestre(path)


def tabela_mestre_cached(path: str) -> pd.DataFrame:
    return _carregar(path, os.path.getmtime(path))
