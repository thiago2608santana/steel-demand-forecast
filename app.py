"""Interface Streamlit do projeto de previsão de demanda de aços longos.

Execute a partir da raiz do projeto:
    uv run streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Steel Demand Forecast",
    page_icon="🏗️",
    layout="wide",
)

from ui import tab_inferencia, tab_ingestao, tab_resultados, tab_treino  # noqa: E402
from ui.estado import inicializar_estado  # noqa: E402

inicializar_estado()

st.title("🏗️ Previsão de Demanda de Aços Longos")

aba_ingestao, aba_treino, aba_resultados, aba_inferencia = st.tabs([
    "📥 Ingestão de dados",
    "⚙️ Parâmetros e treino",
    "📊 Resultados do treino",
    "🔮 Inferência",
])

with aba_ingestao:
    tab_ingestao.render()
with aba_treino:
    tab_treino.render()
with aba_resultados:
    tab_resultados.render()
with aba_inferencia:
    tab_inferencia.render()
