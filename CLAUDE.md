# CLAUDE.md — Steel Demand Forecast

## O que é este projeto

Pipeline ETL + modelagem de previsão de demanda de aços longos no Brasil. Consome APIs públicas do governo (IPEA, BCB, IBGE/SIDRA) e arquivos manuais do setor siderúrgico (ANFAVEA, IABr, CNO). A persistência segue a arquitetura medalhão em tabelas Delta no Databricks (Unity Catalog, catálogo `steeldemand`): dados crus em `steeldemand.bronze.*`, transformados em `steeldemand.silver.*` e a tabela mestre mensal em `steeldemand.gold.tabela_mestre` — input dos modelos de machine learning. `dados/raw/` existe apenas como staging local dos arquivos manuais.

## Como rodar

Pré-requisito (uma vez): Databricks CLI autenticado (`databricks auth login`), profile apontado em `databricks.profile` no `config.yaml` e catálogo criado (`CREATE CATALOG IF NOT EXISTS steeldemand`). O compute é serverless por padrão (`databricks.serverless`).

```bash
uv sync
python run_etl.py                          # todos os pipelines
python run_etl.py anfavea cno performance  # só os que dependem de arquivos manuais
python run_etl.py macro                    # só as APIs (demora ~10 min pelo SIDRA)
python run_etl.py tabela_mestre            # consolida silver → gold
uv run streamlit run app.py                # interface Streamlit (ingestão, treino, resultados, inferência)
```

## Estrutura de código

- **`run_etl.py`** — orquestrador; registra todos os pipelines no dict `PIPELINES`
- **`config.yaml`** — fonte única de verdade para paths de input, conexão Databricks (profile/catálogo), datas, códigos de API e filtros
- **`config.py`** — carrega o YAML e expõe `CFG`; não editar diretamente
- **`etl/`** — um arquivo por fonte de dados; cada pipeline recebe `cfg: dict` como único argumento
- **`ml/`** — pipeline de ML modularizado a partir do `pipeline_ml.ipynb` (só XGBoost+Optuna; SARIMA/SARIMAX ficam no notebook). Lógica pura, sem imports de Streamlit: `parametros.py` (dataclass `ParametrosML` com os defaults do notebook), `features.py`, `treino.py` (fachada `PipelineML`), `forecast.py` (previsão recursiva), `persistencia.py` (sessões em `secoes/resultados_{ts}/` com modelo XGBoost em JSON nativo, não pickle) e `plots.py` (gráficos Plotly)
- **`app.py` + `ui/`** — interface Streamlit com 4 abas (um módulo por aba em `ui/tab_*.py`); estado entre abas via `st.session_state` (chaves em `ui/estado.py`); logs do ETL/treino capturados por `ui/log_streamlit.py`
- **`utils/databricks_io.py`** — único ponto de contato com o Databricks: `get_spark()` (sessão via databricks-connect), `salvar_tabela(df, camada, tabela)` (overwrite full refresh + coluna de auditoria `ingestion_ts`), `ler_tabela`, `tabela_existe`, `ultima_modificacao` e `nome_completo`
- **`utils/transforms.py`** — funções compartilhadas de limpeza/transformação (SIDRA, datas, Excel)
- **`utils/viz.py`** — helpers de formatação para gráficos matplotlib do ETL (os plots Plotly do ML ficam em `ml/plots.py`)
- **`notebooks/pipeline_ml.ipynb`** — pipeline completo de modelagem: feature engineering, seleção de variáveis, SARIMA, SARIMAX e XGBoost com Optuna; inclui previsão recursiva para horizonte futuro
- **`notebooks/tabela_mestre.ipynb`** — replica o pipeline gold de forma interativa
- **`notebooks/`** — demais notebooks de exploração por fonte de dados

## Convenções importantes

### Adicionar um novo pipeline

1. Criar `etl/<nome>.py` com função `processar_<nome>(cfg: dict) -> pd.DataFrame`
2. Se a fonte for arquivo manual, adicionar o path de input em `config.yaml` (`paths`)
3. Salvar o dado cru com `salvar_tabela(df, "bronze", "<tabela>")` e o transformado com `salvar_tabela(df, "silver", "<tabela>")` (de `utils.databricks_io`)
4. Registrar no dict `PIPELINES` em `run_etl.py`
5. Documentar as colunas e os nomes das tabelas em `docs/dicionario_de_dados.md`

### Assinatura das funções ETL

Todas as funções públicas dos pipelines recebem `cfg: dict` (nunca `cfg=None`). O `CFG` global é injetado pelo `run_etl.py`. Não usar o padrão `if cfg is None: cfg = CFG` — esse padrão foi removido no refactor.

### Imports de utils

Importar sempre de `utils.transforms`, `utils.databricks_io` ou `utils.viz` diretamente, não de `utils` (o `__init__.py` re-exporta tudo, mas imports explícitos são preferidos para rastreabilidade).

```python
from utils.databricks_io import salvar_tabela
from utils.transforms import filter_by_date, validar_output
```

### Dados não são versionados

A pasta `dados/raw/` está no `.gitignore` e serve só de staging: arquivos manuais devem ser obtidos nas fontes listadas no `README.md` e colocados lá. As camadas bronze/silver/gold vivem no Databricks, não no repositório.

### config.yaml — campos sensíveis

- `filters.date_end` — atualizar a cada novo ciclo de dados
- `paths.performance_input` — atualizar ao trocar o arquivo mensal do IABr
- `databricks.profile` — nome do profile no `~/.databrickscfg`; `databricks.serverless` liga/desliga o compute serverless
- `api.bcb.selic_periodo_*` — define a janela de coleta da SELIC diária em dois lotes (limitação da API do BCB)

## Dependências externas relevantes

| Biblioteca | Uso |
|---|---|
| `databricks-connect` | Sessão Spark remota — leitura/escrita das tabelas Delta no Unity Catalog |
| `ipeadatapy` | API do IPEA Data |
| `python-bcb` | API do Banco Central (SGS) |
| `sidrapy` | API do SIDRA/IBGE |
| `openpyxl` | Leitura e escrita de `.xlsx` |
| `pandas` | Transformações e merges |
| `pyyaml` | Carregamento do `config.yaml` |
| `statsmodels` | SARIMA e SARIMAX (`tsa.statespace.sarimax.SARIMAX`) |
| `xgboost` | Modelo XGBoost (`XGBRegressor`) |
| `optuna` | Tuning de hiperparâmetros do XGBoost |
| `scikit-learn` | Métricas, `TimeSeriesSplit`, `permutation_importance` |

## Armadilhas conhecidas

- **SIDRA é lento**: a coleta por UF faz 27 requisições com sleep de 0.5s entre elas. O pipeline `macro` pode levar 10–15 minutos no total.
- **ANFAVEA usa cabeçalho mesclado**: o Excel tem layout de duas linhas de cabeçalho com células mescladas. A função `_renomear_colunas` em `etl/anfavea.py` trata isso ciclando o índice de variável a cada `len(variaveis)` colunas.
- **CNO usa encoding latin-1**: o CSV do governo vem em latin-1, não UTF-8.
- **Performance usa formato wide**: o `.xls` do IABr tem anos e meses em linhas separadas com forward-fill. O parser localiza essas linhas dinamicamente pelo conteúdo.
- **Tabela mestre usa left join**: o merge em `etl/tabela_mestre.py` é left (ancorado no alvo), com `ffill`/`bfill` aplicado às colunas numéricas para preencher lacunas onde uma feature começa depois do alvo. Valores ausentes do SIDRA (`-`, `...`) viram `NaN` em `ajustar_valores`, não `0.0`.
- **Colunas com espaços/acentos/`\n` nas tabelas Delta**: bronze e silver preservam nomes originais (ex.: `"AUTOVEÍCULOS TOTAL_Produção"`, especificações do IABr com quebra de linha). Isso só funciona porque `salvar_tabela` grava com `delta.columnMapping.mode = name` — não remover essa option.
- **Colunas object viram string no bronze**: `_preparar_para_spark` converte colunas `object` (tipos mistos dos arquivos crus) para string antes do upload. Nas silver, tipar explicitamente (`pd.to_numeric`/`pd.to_datetime`, como em `etl/anfavea.py` e `etl/performance.py`) para não gravar números como texto.
- **SARIMA supera XGBoost no teste**: com os dados atuais (~149 obs), o SARIMA(1,1,2)×(0,1,1,12) tem MAPE~5.4% e R²~0.52 no teste, enquanto o XGBoost fica em MAPE~5.8% e R²~0.20. As features externas não generalizam para o período de teste — não é problema de hiperparâmetros. O SARIMAX com muitos regressores piora ainda mais (R² negativo). Adicionar mais histórico ou features com lead time comprovado é o próximo passo natural.
- **Permutation importance em val pequeno é ruído**: com val de 12 obs a seleção de features por permutation importance é estatisticamente não-confiável (std ≈ mean). Usar val de pelo menos 24-36 obs ou walk-forward CV para seleção.
