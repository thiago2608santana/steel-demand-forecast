"""Gráficos Plotly do pipeline de ML — versões interativas dos plots do notebook.

Todas as funções retornam go.Figure prontas para st.plotly_chart.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from ml.forecast import ResultadoForecast
from ml.treino import SPLITS, ResultadoTreino

CORES_SPLIT = {"train": "steelblue", "val": "green", "test": "crimson"}
ROTULOS_SPLIT = {"train": "Treino", "val": "Val", "test": "Teste"}


def _vline(fig: go.Figure, x, cor: str) -> None:
    """Linha vertical pontilhada compatível com eixo datetime."""
    fig.add_shape(
        type="line", x0=x, x1=x, y0=0, y1=1, yref="paper",
        line=dict(color=cor, dash="dot", width=1.5), opacity=0.6,
    )


def plot_serie_historica(df: pd.DataFrame, target_col: str) -> go.Figure:
    """Evolução do target ao longo do tempo (sanidade na aba de ingestão)."""
    fig = go.Figure(go.Scatter(
        x=df["data"], y=df[target_col], mode="lines+markers",
        marker=dict(size=4), line=dict(color="steelblue"),
        name=target_col,
    ))
    fig.update_layout(
        title="Evolução do Consumo Aparente ao Longo do Tempo",
        xaxis_title="Data", yaxis_title="Consumo Aparente (Mil t)",
        hovermode="x unified", height=420,
    )
    return fig


def plot_real_x_predito(resultado: ResultadoTreino) -> go.Figure:
    """Real vs previsto com cores distintas para treino, validação e teste."""
    fig = go.Figure()
    for s in SPLITS:
        datas = resultado.splits.datas(s)
        cor, rotulo = CORES_SPLIT[s], ROTULOS_SPLIT[s]
        fig.add_trace(go.Scatter(
            x=datas, y=resultado.splits.y(s), mode="lines+markers",
            name=f"Real ({rotulo})", line=dict(color=cor),
            marker=dict(size=5),
        ))
        fig.add_trace(go.Scatter(
            x=datas, y=resultado.predicoes[s], mode="lines+markers",
            name=f"Previsto ({rotulo})", line=dict(color=cor, dash="dash"),
            marker=dict(symbol="x", size=6), opacity=0.75,
        ))

    _vline(fig, pd.Timestamp(resultado.params.data_inicio_val), CORES_SPLIT["val"])
    _vline(fig, pd.Timestamp(resultado.params.data_inicio_teste), CORES_SPLIT["test"])

    r2 = {s: resultado.metrica(s, "R²") for s in SPLITS}
    mape_test = resultado.metrica("test", "MAPE")
    fig.update_layout(
        title=(
            "Consumo Aparente de Aço: Real vs Previsto<br>"
            f"<sup>R² Treino={r2['train']:.3f} | R² Val={r2['val']:.3f} | "
            f"R² Teste={r2['test']:.3f} | MAPE Teste={mape_test:.2%}</sup>"
        ),
        xaxis_title="Tempo", yaxis_title="Consumo Aparente (Mil t)",
        hovermode="x unified", height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def plot_importancias(resultado: ResultadoTreino, top_n: int = 20) -> go.Figure:
    """Top N features mais importantes do XGBoost (ganho de split)."""
    importancias = (
        pd.Series(resultado.modelo.feature_importances_, index=resultado.feature_cols)
        .sort_values()
        .tail(top_n)
    )
    fig = go.Figure(go.Bar(
        x=importancias.values, y=importancias.index, orientation="h",
        marker_color="steelblue",
    ))
    fig.update_layout(
        title=f"Top {min(top_n, len(importancias))} Features mais Importantes (XGBoost)",
        xaxis_title="Importância", yaxis_title="Feature",
        height=max(400, 26 * len(importancias)),
    )
    return fig


def plot_residuos(resultado: ResultadoTreino) -> go.Figure:
    """Análise de resíduos em 4 painéis: tempo, vs previsto, histograma e Q-Q."""
    residuos = resultado.residuos
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Resíduos ao Longo do Tempo",
            "Resíduos vs Valores Previstos",
            "Distribuição dos Resíduos — Teste",
            "Q-Q Plot dos Resíduos — Teste",
        ),
    )

    for s in SPLITS:
        cor, rotulo = CORES_SPLIT[s], ROTULOS_SPLIT[s]
        fig.add_trace(go.Scatter(
            x=resultado.splits.datas(s), y=residuos[s], mode="markers",
            name=rotulo, legendgroup=s, marker=dict(color=cor, size=6),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=resultado.predicoes[s], y=residuos[s], mode="markers",
            name=rotulo, legendgroup=s, showlegend=False,
            marker=dict(color=cor, size=6, opacity=0.7),
        ), row=1, col=2)

    fig.add_trace(go.Histogram(
        x=residuos["test"], nbinsx=10, marker_color="crimson",
        name="Teste", showlegend=False,
    ), row=2, col=1)

    # Q-Q: quantis teóricos da normal vs quantis observados (Plotly não tem pronto)
    (osm, osr), (slope, intercept, _) = stats.probplot(residuos["test"], dist="norm")
    fig.add_trace(go.Scatter(
        x=osm, y=osr, mode="markers", showlegend=False,
        marker=dict(color="crimson", size=6),
    ), row=2, col=2)
    fig.add_trace(go.Scatter(
        x=osm, y=slope * osm + intercept, mode="lines", showlegend=False,
        line=dict(color="black", dash="dash"),
    ), row=2, col=2)

    for row, col in [(1, 1), (1, 2)]:
        fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1,
                      row=row, col=col)

    fig.update_xaxes(title_text="Data", row=1, col=1)
    fig.update_xaxes(title_text="Valor Previsto (Mil t)", row=1, col=2)
    fig.update_xaxes(title_text="Resíduo (Real − Previsto)", row=2, col=1)
    fig.update_xaxes(title_text="Quantis Teóricos", row=2, col=2)
    fig.update_yaxes(title_text="Resíduo", row=1, col=1)
    fig.update_yaxes(title_text="Resíduo", row=1, col=2)
    fig.update_yaxes(title_text="Frequência", row=2, col=1)
    fig.update_yaxes(title_text="Quantis Observados", row=2, col=2)

    fig.update_layout(
        title="Análise de Resíduos — XGBoost", height=760,
        legend=dict(orientation="h", yanchor="bottom", y=1.03),
    )
    return fig


def plot_dispersao(resultado: ResultadoTreino) -> go.Figure:
    """y_real vs y_pred no teste, com a diagonal de previsão perfeita."""
    y_true = resultado.splits.y("test").values
    y_pred = resultado.predicoes["test"]
    lim = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=y_true, y=y_pred, mode="markers", name="Teste",
        marker=dict(color="steelblue", size=8, opacity=0.6),
    ))
    fig.add_trace(go.Scatter(
        x=lim, y=lim, mode="lines", name="Previsão perfeita",
        line=dict(color="red", dash="dash"),
    ))
    fig.update_layout(
        title="Validação do Modelo: y_real vs y_pred (Teste)",
        xaxis_title="Valor Real (Mil t)", yaxis_title="Valor Predito (Mil t)",
        height=460,
    )
    return fig


def plot_forecast(forecast: ResultadoForecast, janela_hist: int = 36) -> go.Figure:
    """Histórico recente + previsão recursiva + faixa de incerteza ±MAE×√h."""
    hist_ctx = forecast.hist.iloc[-janela_hist:]
    fc = forecast.forecast_df
    superior = fc["Previsao"] + forecast.error_bands
    inferior = fc["Previsao"] - forecast.error_bands

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist_ctx.index, y=hist_ctx.values, mode="lines+markers",
        name=f"Histórico (últimos {len(hist_ctx)} meses)",
        line=dict(color="steelblue"), marker=dict(size=4),
    ))
    fig.add_trace(go.Scatter(
        x=fc["Data"], y=superior, mode="lines",
        line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=fc["Data"], y=inferior, mode="lines",
        line=dict(width=0), fill="tonexty",
        fillcolor="rgba(255,140,0,0.18)",
        name=f"Faixa de incerteza (±MAE × √h, MAE teste = {forecast.mae_ref:.0f} Mil t)",
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=fc["Data"], y=fc["Previsao"], mode="lines+markers",
        name=f"Previsão recursiva ({len(fc)} meses)",
        line=dict(color="darkorange", dash="dash", width=2),
        marker=dict(symbol="triangle-up", size=8),
    ))
    _vline(fig, forecast.ultima_data, "gray")

    fig.update_layout(
        title=f"Consumo Aparente de Aços Longos — Previsão {len(fc)} meses à frente",
        xaxis_title="Mês", yaxis_title="Consumo Aparente (Mil t)",
        hovermode="x unified", height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig
