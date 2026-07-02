"""Aba 3 — Resultados do treinamento: métricas, importâncias, resíduos e real x predito."""
from pathlib import Path

import numpy as np
import streamlit as st

from ml import plots
from ui.sessoes import selecionar_e_carregar_sessao


def render() -> None:
    resultado = st.session_state["resultado_treino"]
    if resultado is None:
        st.info(
            "Nenhum modelo em memória. Treine na aba **Parâmetros e treino** "
            "ou carregue uma sessão salva abaixo."
        )
        if selecionar_e_carregar_sessao("resultados"):
            st.rerun()
        return

    path_sessao = st.session_state["path_sessao"]
    if path_sessao:
        st.caption(f"Sessão: `{path_sessao}`")

    st.subheader("Métricas por conjunto")
    st.dataframe(resultado.metricas, use_container_width=True)
    if resultado.cv_mapes:
        st.caption(
            f"Walk-forward CV MAPE: {np.mean(resultado.cv_mapes):.4f} "
            f"± {np.std(resultado.cv_mapes):.4f} ({len(resultado.cv_mapes)} folds)"
        )

    st.subheader("Real vs Previsto")
    st.plotly_chart(plots.plot_real_x_predito(resultado), use_container_width=True)

    aba_imp, aba_res, aba_disp = st.tabs(
        ["Importância de variáveis", "Análise de resíduos", "Dispersão (teste)"]
    )
    with aba_imp:
        top_n = st.slider("Top N features", 5, len(resultado.feature_cols), 20)
        st.plotly_chart(plots.plot_importancias(resultado, top_n), use_container_width=True)
    with aba_res:
        st.plotly_chart(plots.plot_residuos(resultado), use_container_width=True)
    with aba_disp:
        st.plotly_chart(plots.plot_dispersao(resultado), use_container_width=True)

    if path_sessao:
        valid_data = Path(path_sessao) / "valid_data.xlsx"
        if valid_data.exists():
            st.download_button(
                "⬇️ Baixar dados da execução (valid_data.xlsx)",
                data=valid_data.read_bytes(),
                file_name=f"valid_data_{Path(path_sessao).name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
