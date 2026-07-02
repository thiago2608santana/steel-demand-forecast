"""Pipeline de machine learning modularizado a partir de notebooks/pipeline_ml.ipynb.

Módulos:
    parametros   — dataclass ParametrosML com os parâmetros globais do notebook
    features     — carga da tabela mestre, feature engineering e seleção de features
    treino       — splits temporais, Optuna, walk-forward CV, modelo final e métricas
    forecast     — previsão recursiva multi-step com banda de incerteza
    persistencia — salvar/carregar sessões de treino em secoes/resultados_{timestamp}/
    plots        — gráficos Plotly consumidos pela interface Streamlit
"""
