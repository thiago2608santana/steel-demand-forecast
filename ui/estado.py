"""Estado compartilhado entre as abas via st.session_state."""
import streamlit as st

CHAVES_DEFAULT = {
    "resultado_treino": None,    # ResultadoTreino do treino atual ou sessão carregada
    "resultado_forecast": None,  # ResultadoForecast da última inferência
    "path_sessao": None,         # Path do diretório secoes/resultados_{ts} em uso
    "em_execucao": False,        # trava botões durante ETL/treino
}


def inicializar_estado() -> None:
    for chave, default in CHAVES_DEFAULT.items():
        st.session_state.setdefault(chave, default)
