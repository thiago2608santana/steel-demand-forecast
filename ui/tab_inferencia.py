"""Aba 4 — Inferência: previsão recursiva com horizonte real e faixa de incerteza."""
import io

import streamlit as st

from ml import plots
from ml.forecast import prever_recursivo
from ml.persistencia import salvar_forecast
from ui.sessoes import selecionar_e_carregar_sessao


def render() -> None:
    resultado = st.session_state["resultado_treino"]
    if resultado is None:
        st.info(
            "Nenhum modelo em memória. Treine na aba **Parâmetros e treino** "
            "ou carregue uma sessão salva abaixo."
        )
        if selecionar_e_carregar_sessao("inferencia"):
            st.rerun()
        return

    path_sessao = st.session_state["path_sessao"]
    st.caption(f"Modelo em uso: `{path_sessao or 'treino da sessão atual'}`")
    with st.expander("Trocar de sessão salva"):
        if selecionar_e_carregar_sessao("inferencia_troca"):
            st.rerun()

    col1, col2 = st.columns(2)
    horizonte = col1.number_input(
        "Horizonte de previsão (meses)", 1, 36, resultado.params.n_horizons
    )
    janela_hist = col2.slider(
        "Meses de histórico no gráfico", 12, 60, resultado.params.janela_plot_historico
    )

    if st.button("🔮 Gerar previsão", type="primary", disabled=st.session_state["em_execucao"]):
        with st.spinner("Retreinando no histórico completo e projetando..."):
            forecast = prever_recursivo(resultado, int(horizonte))
        st.session_state["resultado_forecast"] = forecast
        if path_sessao:
            salvar_forecast(path_sessao, forecast)

    forecast = st.session_state["resultado_forecast"]
    if forecast is None:
        return

    st.plotly_chart(plots.plot_forecast(forecast, janela_hist), use_container_width=True)
    st.caption(
        "Lags e médias móveis do consumo são atualizados recursivamente com as próprias "
        "previsões; as variáveis externas ficam congeladas no último valor observado. "
        "A faixa de incerteza é ±MAE(teste) × √h."
    )

    tabela = forecast.tabela()
    st.dataframe(tabela, use_container_width=True, hide_index=True)

    buffer = io.BytesIO()
    tabela.to_excel(buffer, index=False, engine="openpyxl")
    st.download_button(
        "⬇️ Baixar previsão (xlsx)",
        data=buffer.getvalue(),
        file_name=f"forecast_{len(forecast.forecast_df)}m.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
