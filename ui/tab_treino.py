"""Aba 2 — Parâmetros do modelo e treinamento do XGBoost com Optuna."""
import datetime as dt

import numpy as np
import streamlit as st

from ml.parametros import ParametrosML
from ml.persistencia import salvar_sessao
from ml.treino import PipelineML
from ui.dados import tabela_mestre_cached
from ui.log_streamlit import capturar_logs
from utils.databricks_io import nome_completo, tabela_existe

DEFAULTS = ParametrosML()


def _widgets_parametros(df) -> ParametrosML:
    """Renderiza os widgets e devolve o ParametrosML correspondente."""
    data_min, data_max = df["data"].min().date(), df["data"].max().date()
    cols_numericas = [
        c for c in df.select_dtypes(include="number").columns if c != DEFAULTS.target_col
    ]

    with st.expander("📅 Dados e splits temporais", expanded=True):
        col1, col2 = st.columns(2)
        data_val = col1.date_input(
            "Início da validação",
            dt.date.fromisoformat(DEFAULTS.data_inicio_val),
            min_value=data_min, max_value=data_max,
            help="Treino = tudo antes desta data.",
        )
        data_teste = col2.date_input(
            "Início do teste",
            dt.date.fromisoformat(DEFAULTS.data_inicio_teste),
            min_value=data_min, max_value=data_max,
            help="Teste fica isolado até a avaliação final.",
        )

    with st.expander("🛠️ Feature engineering"):
        lags_consumo = st.multiselect(
            "Lags do consumo (meses)", list(range(1, 13)), DEFAULTS.lags_consumo
        )
        col1, col2 = st.columns(2)
        cols_macro = col1.multiselect(
            "Variáveis macro com lags",
            cols_numericas,
            [c for c in DEFAULTS.cols_macro if c in cols_numericas],
        )
        lags_macro = col2.multiselect(
            "Lags das variáveis macro (meses)", list(range(1, 13)), DEFAULTS.lags_macro
        )
        janelas = st.multiselect(
            "Janelas de média móvel do consumo (meses)",
            [3, 6, 9, 12, 18, 24],
            DEFAULTS.janelas_media_movel,
        )

    with st.expander("🔍 Seleção de features"):
        thr_multi = st.slider(
            "Limiar de multicolinearidade (|corr| mútua)",
            0.50, 1.00, DEFAULTS.threshold_multicolinearidade, 0.01,
        )
        thr_corr = st.slider(
            "Limiar mínimo de |corr| com o target",
            0.00, 0.50, DEFAULTS.threshold_corr_target, 0.01,
        )
        usar_perm = st.checkbox(
            "Seleção por permutation importance no val",
            DEFAULTS.usar_permutation_importance,
            help=(
                "Desativada por padrão: com conjunto de validação pequeno a "
                "seleção por permutação é estatisticamente ruidosa."
            ),
        )

    with st.expander("⚡ Otimização e pesos"):
        lambda_fator = st.slider(
            "Fator de decaimento por recência (λ)", 0.80, 1.00, DEFAULTS.lambda_fator, 0.01,
            help="Peso das observações decai exponencialmente com a idade; 1.0 = sem pesos.",
        )
        col1, col2 = st.columns(2)
        n_trials = col1.number_input(
            "Trials do Optuna", 5, 500, DEFAULTS.optuna_n_trials,
            help="Mais trials = busca mais completa, treino mais demorado.",
        )
        early = col2.number_input(
            "Early stopping rounds", 5, 100, DEFAULTS.optuna_early_stopping_rounds
        )
        wf_splits = col1.number_input(
            "Walk-forward: nº de folds", 2, 12, DEFAULTS.walk_forward_n_splits
        )
        wf_test = col2.number_input(
            "Walk-forward: meses por fold", 1, 12, DEFAULTS.walk_forward_test_size
        )

    return ParametrosML(
        data_inicio_val=data_val.isoformat(),
        data_inicio_teste=data_teste.isoformat(),
        lags_consumo=sorted(lags_consumo),
        lags_macro=sorted(lags_macro),
        cols_macro=cols_macro,
        janelas_media_movel=sorted(janelas),
        threshold_multicolinearidade=thr_multi,
        threshold_corr_target=thr_corr,
        usar_permutation_importance=usar_perm,
        lambda_fator=lambda_fator,
        optuna_n_trials=int(n_trials),
        optuna_early_stopping_rounds=int(early),
        walk_forward_n_splits=int(wf_splits),
        walk_forward_test_size=int(wf_test),
    )


def _treinar(params: ParametrosML) -> None:
    st.session_state["em_execucao"] = True
    try:
        with st.status("Treinando XGBoost + Optuna...", expanded=True) as status:
            barra = st.progress(0.0, text="Preparando dados...")
            log_area = st.empty()

            def cb(study, trial):
                frac = (trial.number + 1) / params.optuna_n_trials
                barra.progress(
                    min(frac, 1.0),
                    text=(
                        f"Trial {trial.number + 1}/{params.optuna_n_trials} — "
                        f"melhor MSE (val): {study.best_value:,.0f}"
                    ),
                )

            with capturar_logs(log_area):
                resultado = PipelineML(params).treinar(trial_callback=cb)
                barra.progress(1.0, text="Otimização concluída — salvando sessão...")
                path_sessao = salvar_sessao(resultado)

            status.update(label=f"Treino concluído — sessão `{path_sessao.name}`", state="complete")
    except ValueError as exc:
        st.session_state["em_execucao"] = False
        st.error(f"Parâmetros inválidos: {exc}")
        return
    finally:
        st.session_state["em_execucao"] = False

    st.session_state["resultado_treino"] = resultado
    st.session_state["path_sessao"] = path_sessao
    st.session_state["resultado_forecast"] = None
    st.toast("Treino concluído — veja a aba Resultados do treino", icon="🎉")


def render() -> None:
    tabela_gold = nome_completo("gold", "tabela_mestre")
    if not tabela_existe("gold", "tabela_mestre"):
        st.error(
            f"Tabela mestre não encontrada no Databricks (`{tabela_gold}`). "
            "Gere-a na aba **Ingestão de dados** antes de treinar."
        )
        return

    df = tabela_mestre_cached()
    st.caption(
        f"Base: `{tabela_gold}` — {df.shape[0]} meses "
        f"({df['data'].min().date()} → {df['data'].max().date()})"
    )

    params = _widgets_parametros(df)

    if st.button(
        "🚀 Treinar modelo",
        type="primary",
        disabled=st.session_state["em_execucao"],
    ):
        _treinar(params)

    resultado = st.session_state["resultado_treino"]
    if resultado is not None:
        st.divider()
        st.subheader("Último treino")
        sessao = st.session_state["path_sessao"]
        if sessao:
            st.caption(f"Sessão: `{sessao}`")
        st.dataframe(resultado.metricas, use_container_width=True)
        if resultado.cv_mapes:
            st.caption(
                f"Walk-forward CV MAPE: {np.mean(resultado.cv_mapes):.4f} "
                f"± {np.std(resultado.cv_mapes):.4f}"
            )
