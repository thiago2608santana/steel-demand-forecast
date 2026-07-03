# Steel Demand Forecast

Projeto de previsão de demanda de aços longos no Brasil, combinando dados de fontes públicas do governo com arquivos manuais do setor siderúrgico. O pipeline ETL persiste as camadas da arquitetura medalhão como tabelas Delta no Databricks (Unity Catalog, catálogo `steeldemand`) e consolida séries temporais mensais na tabela mestre `steeldemand.gold.tabela_mestre`, que serve de input para modelos de machine learning.

---

## Estrutura do Projeto

```
steel-demand-forecast/
├── config.py              # Carregador do config.yaml
├── config.yaml            # Configuração centralizada (paths, filtros, parâmetros de API)
├── run_etl.py             # Orquestrador — ponto de entrada do pipeline
├── app.py                 # Interface Streamlit (ingestão, treino, resultados, inferência)
│
├── etl/                   # Pipelines de extração e transformação
│   ├── anfavea.py         # Produção de veículos (ANFAVEA)
│   ├── cno.py             # Cadastro Nacional de Obras (Receita Federal)
│   ├── macroeconomia.py   # IPEA, BCB/SGS e SIDRA/IBGE
│   ├── performance.py     # Performance mensal do setor siderúrgico (IABr)
│   └── tabela_mestre.py   # Consolida silver → tabela mestre (gold)
│
├── ml/                    # Pipeline de ML modularizado (a partir do pipeline_ml.ipynb)
│   ├── parametros.py      # Dataclass ParametrosML (defaults do notebook)
│   ├── features.py        # Feature engineering e seleção de features
│   ├── treino.py          # Splits, Optuna, walk-forward CV e métricas
│   ├── forecast.py        # Previsão recursiva multi-step
│   ├── persistencia.py    # Salvar/recarregar sessões em secoes/
│   └── plots.py           # Gráficos Plotly
│
├── ui/                    # Componentes Streamlit — um módulo por aba
│
├── utils/
│   ├── databricks_io.py   # Persistência no Databricks (Unity Catalog) via databricks-connect
│   ├── transforms.py      # Funções de limpeza e transformação de dados
│   └── viz.py             # Funções de formatação para visualizações
│
├── notebooks/             # Análise exploratória e modelagem
│   ├── pipeline_ml.ipynb          # Pipeline completo de ML: feature eng, SARIMA, SARIMAX, XGBoost
│   ├── tabela_mestre.ipynb        # Versão interativa da construção da tabela mestre
│   ├── exploracao.ipynb
│   ├── exploracao_anfavea.ipynb
│   └── exploracao_cno.ipynb
│
├── dados/
│   └── raw/               # Staging local dos arquivos manuais de entrada (não versionados)
│
└── docs/
    ├── dicionario_de_dados.md   # Descrição de todas as fontes e colunas
    └── fluxo_ml.md              # Diagramas do fluxo de ML (pacote ml/)
```

---

## Fontes de Dados

| Fonte | Tipo | Dados |
|---|---|---|
| [ANFAVEA](https://anfavea.com.br/site/edicoes-em-excel/) | Manual (xlsx) | Produção de veículos automotores |
| [CNO / Receita Federal](https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-de-obras-cno) | Manual (csv) | Área de obras registradas por unidade |
| [IABr — Performance Mensal](https://acobrasil.org.br/site/estatisticas/) | Manual (xls) | Produção, consumo e comércio de aço |
| [IPEA Data](http://www.ipeadata.gov.br) | API (`ipeadatapy`) | SELIC anual, câmbio, FBC |
| [BCB / SGS](https://www3.bcb.gov.br/sgspub/) | API (`python-bcb`) | IPCA, PIB mensal, crédito industrial |
| [SIDRA / IBGE](https://sidra.ibge.gov.br) | API (`sidrapy`) | SINAPI, PIM-PF, IPP, PNAD Contínua |

---

## Como Executar

### Pré-requisitos

```bash
# Instalar dependências com uv
uv sync
```

**Databricks (uma única vez):** as camadas bronze/silver/gold são gravadas no Unity Catalog via `databricks-connect`.

1. Instale o [Databricks CLI](https://docs.databricks.com/dev-tools/cli/) e autentique: `databricks auth login --host <workspace-url>`
2. Confira o nome do profile em `~/.databrickscfg` e ajuste `databricks.profile` no `config.yaml` (o compute padrão é serverless; `databricks.serverless: false` volta a exigir `cluster_id` no profile)
3. Crie o catálogo no workspace: `CREATE CATALOG IF NOT EXISTS steeldemand`

### 1. Atualizar arquivos manuais

Antes de rodar o ETL, coloque os arquivos atualizados em `dados/raw/`:

| Arquivo | Pipeline |
|---|---|
| `anfavea_autoveiculos.xlsx` | `anfavea` |
| `Performance-Mensal_<ano.mes>.xls` | `performance` |
| `cno.csv` | `cno` |

> Lembre de atualizar o caminho `performance_input` em `config.yaml` quando trocar o arquivo de performance.

### 2. Executar o pipeline

```bash
# Todos os pipelines em sequência
python run_etl.py

# Pipelines individuais
python run_etl.py anfavea
python run_etl.py cno
python run_etl.py performance
python run_etl.py macro
python run_etl.py tabela_mestre

# Combinações
python run_etl.py anfavea cno performance
```

**Ordem recomendada para execução completa:**

```bash
python run_etl.py anfavea cno performance  # arquivos manuais primeiro
python run_etl.py macro                    # APIs públicas (pode demorar ~10 min)
python run_etl.py tabela_mestre            # gera o input do modelo
```

### 3. Output

Cada pipeline grava duas camadas no Databricks: os dados crus em `steeldemand.bronze.*` (arquivos manuais e respostas de API como chegam) e os dados transformados em `steeldemand.silver.*`. A tabela mestre é salva em `steeldemand.gold.tabela_mestre` com ~149 observações mensais e 32 colunas (1 variável alvo + 31 features). O mapa completo de tabelas está no [dicionário de dados](docs/dicionario_de_dados.md).

---

## Interface Streamlit

```bash
uv run streamlit run app.py
```

A interface tem quatro abas:

1. **📥 Ingestão de dados** — upload dos arquivos manuais (ANFAVEA, CNO, IABr) direto para `dados/raw/`, execução dos pipelines ETL com logs ao vivo e prévia da tabela mestre.
2. **⚙️ Parâmetros e treino** — expõe os parâmetros globais do notebook (datas de split, lags, thresholds de seleção, trials do Optuna etc.) e treina o XGBoost com barra de progresso.
3. **📊 Resultados do treino** — métricas por conjunto, real vs previsto (treino/val/teste), importância de variáveis e análise de resíduos.
4. **🔮 Inferência** — previsão recursiva com horizonte configurável (1–36 meses) e faixa de incerteza ±MAE×√h.

Cada treino gera uma sessão em `secoes/resultados_{timestamp}/` (modelo XGBoost em formato nativo, parâmetros, métricas, dados e previsão), que pode ser recarregada nas abas de resultados e inferência mesmo após reiniciar o app. A lógica de modelagem vive no pacote `ml/` — o notebook `pipeline_ml.ipynb` continua sendo a referência exploratória (SARIMA/SARIMAX inclusos).

---

## Configuração

Todos os parâmetros ficam em `config.yaml`:

- **`paths`** — caminhos dos arquivos manuais de entrada (staging em `dados/raw/`)
- **`databricks`** — profile do `~/.databrickscfg`, uso de serverless e catálogo de destino
- **`filters`** — intervalo de datas (`date_start` / `date_end`)
- **`api`** — códigos de séries do IPEA, BCB e SIDRA
- **`geo`** — códigos de UF para coleta do SIDRA
- **`sectors`** — seções industriais filtradas no PIM-PF e IPP
- **`anfavea`** — categorias e variáveis do layout do Excel
- **`cno`** — colunas e filtros geográficos do CSV

---

## Documentação

- [`docs/dicionario_de_dados.md`](docs/dicionario_de_dados.md) — descrição detalhada de todas as fontes, colunas e da tabela mestre
- [`docs/fluxo_ml.md`](docs/fluxo_ml.md) — diagramas do pipeline de ML (`ml/`): treino, previsão recursiva, sessões e integração com a UI
