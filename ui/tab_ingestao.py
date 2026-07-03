"""Aba 1 — Ingestão de dados: upload dos arquivos manuais e execução dos pipelines ETL."""
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import CFG
from ml import plots
from run_etl import PIPELINES  # o import também configura o logging INFO do ETL
from ui.dados import tabela_mestre_cached
from ui.log_streamlit import capturar_logs
from utils.databricks_io import nome_completo, tabela_existe, ultima_modificacao

ORDEM_RECOMENDADA = ["anfavea", "cno", "performance", "macro", "tabela_mestre"]

# rótulo → (chave em CFG["paths"], extensões aceitas)
UPLOADS = {
    "ANFAVEA — produção de autoveículos": ("anfavea_input", ["xlsx"]),
    "CNO — Cadastro Nacional de Obras": ("cno_input", ["csv"]),
    "IABr — Performance Mensal (consumo de aço)": ("performance_input", ["xls"]),
}


def _mtime_legivel(path: str) -> str:
    if not os.path.exists(path):
        return "arquivo ausente"
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d/%m/%Y %H:%M")


def _secao_uploads() -> None:
    st.subheader("Arquivos manuais")
    st.caption(
        "Os uploads são salvos em `dados/raw/` com o nome esperado pelo `config.yaml`, "
        "independentemente do nome original do arquivo."
    )
    for rotulo, (chave_cfg, extensoes) in UPLOADS.items():
        destino = CFG["paths"][chave_cfg]
        col_up, col_info = st.columns([3, 2], vertical_alignment="bottom")
        arquivo = col_up.file_uploader(rotulo, type=extensoes, key=f"upload_{chave_cfg}")
        col_info.caption(f"Destino: `{destino}`\n\nÚltima atualização: {_mtime_legivel(destino)}")
        if arquivo is not None and col_up.button(
            f"Salvar em `{destino}`", key=f"salvar_{chave_cfg}"
        ):
            Path(destino).parent.mkdir(parents=True, exist_ok=True)
            Path(destino).write_bytes(arquivo.getbuffer())
            col_up.success(f"`{arquivo.name}` salvo em `{destino}` ({arquivo.size / 1024:.0f} KB).")

    st.info(
        "O arquivo do IABr muda de nome a cada mês. Ao virar o ciclo, atualize "
        "`paths.performance_input` e `filters.date_end` no `config.yaml`.",
        icon="📅",
    )


def _secao_pipelines() -> None:
    st.subheader("Executar pipelines ETL")
    selecao = st.multiselect(
        "Pipelines",
        ORDEM_RECOMENDADA,
        default=[],
        key="sel_pipelines",
        help="A execução sempre segue a ordem recomendada: manuais → macro → tabela_mestre.",
    )
    st.button(
        "Selecionar todos",
        key="btn_todos",
        on_click=lambda: st.session_state.update(sel_pipelines=list(ORDEM_RECOMENDADA)),
    )

    if "macro" in selecao:
        st.warning(
            "O pipeline **macro** leva 10–15 minutos (27 requisições ao SIDRA). "
            "Não interaja com a interface durante a execução.",
            icon="⏳",
        )

    executar = st.button(
        "▶️ Executar pipelines",
        type="primary",
        disabled=not selecao or st.session_state["em_execucao"],
    )
    if not executar:
        return

    ordenados = [p for p in ORDEM_RECOMENDADA if p in selecao]
    st.session_state["em_execucao"] = True
    erros = []
    try:
        with st.status(f"Executando: {', '.join(ordenados)}", expanded=True) as status:
            log_area = st.empty()
            with capturar_logs(log_area):
                for nome in ordenados:
                    status.update(label=f"Pipeline: {nome}")
                    try:
                        PIPELINES[nome](CFG)
                    except Exception as exc:  # noqa: BLE001 — espelha o run_etl.main
                        erros.append(nome)
                        st.error(f"Falha em `{nome}`: {exc}")
            if erros:
                status.update(label=f"ETL finalizado com erros: {', '.join(erros)}", state="error")
            else:
                status.update(label="ETL concluído com sucesso", state="complete")
    finally:
        st.session_state["em_execucao"] = False

    if not erros:
        st.toast("ETL concluído!", icon="✅")


def _secao_tabela_mestre() -> None:
    tabela_gold = nome_completo("gold", "tabela_mestre")
    st.subheader("Tabela mestre (gold)")
    if not tabela_existe("gold", "tabela_mestre"):
        st.info("Tabela mestre ainda não gerada — execute o pipeline `tabela_mestre`.")
        return

    df = tabela_mestre_cached()
    atualizada = ultima_modificacao("gold", "tabela_mestre")
    atualizada_str = (
        atualizada.astimezone().strftime("%d/%m/%Y %H:%M") if atualizada else "—"
    )
    st.caption(
        f"`{tabela_gold}` — {df.shape[0]} linhas × {df.shape[1]} colunas | "
        f"{df['data'].min().date()} → {df['data'].max().date()} | "
        f"atualizada em {atualizada_str}"
    )
    with st.expander("Prévia dos dados"):
        st.dataframe(df.tail(12), use_container_width=True)
    st.plotly_chart(
        plots.plot_serie_historica(df, "consumo_aparente"), use_container_width=True
    )


def render() -> None:
    _secao_uploads()
    st.divider()
    _secao_pipelines()
    st.divider()
    _secao_tabela_mestre()
