"""Seleção e carga de sessões de treino salvas (compartilhado entre abas)."""
import streamlit as st

from ml.persistencia import carregar_sessao, listar_sessoes


def selecionar_e_carregar_sessao(key: str) -> bool:
    """Selectbox + botão para carregar uma sessão salva. Retorna True se carregou."""
    sessoes = listar_sessoes()
    if not sessoes:
        st.caption("Nenhuma sessão salva encontrada em `secoes/`.")
        return False

    escolha = st.selectbox(
        "Sessão salva", sessoes, format_func=lambda p: p.name, key=f"sel_sessao_{key}"
    )
    if not st.button("Carregar sessão", key=f"btn_sessao_{key}"):
        return False

    with st.spinner(f"Recarregando {escolha.name}..."):
        try:
            resultado = carregar_sessao(escolha)
        except Exception as exc:  # noqa: BLE001 — erro vai para a UI
            st.error(f"Falha ao carregar a sessão: {exc}")
            return False

    st.session_state["resultado_treino"] = resultado
    st.session_state["path_sessao"] = escolha
    st.session_state["resultado_forecast"] = None
    st.success(f"Sessão `{escolha.name}` carregada.")
    return True
