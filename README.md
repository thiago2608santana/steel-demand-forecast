# Steel Demand Forecast

Projeto de previsão de demanda de aços longos no Brasil, combinando dados de fontes públicas do governo com arquivos manuais do setor siderúrgico. O pipeline ETL consolida séries temporais mensais em uma tabela mestre que serve de input para modelos de machine learning.

---

## Estrutura do Projeto

```
steel-demand-forecast/
├── config.py              # Carregador do config.yaml
├── config.yaml            # Configuração centralizada (paths, filtros, parâmetros de API)
├── run_etl.py             # Orquestrador — ponto de entrada do pipeline
│
├── etl/                   # Pipelines de extração e transformação
│   ├── anfavea.py         # Produção de veículos (ANFAVEA)
│   ├── cno.py             # Cadastro Nacional de Obras (Receita Federal)
│   ├── macroeconomia.py   # IPEA, BCB/SGS e SIDRA/IBGE
│   ├── performance.py     # Performance mensal do setor siderúrgico (IABr)
│   └── tabela_mestre.py   # Consolida silver → tabela mestre (gold)
│
├── utils/
│   ├── transforms.py      # Funções de limpeza e transformação de dados
│   └── viz.py             # Funções de formatação para visualizações
│
├── notebooks/             # Análise exploratória e debug
│   ├── exploracao.ipynb
│   ├── exploracao_anfavea.ipynb
│   ├── exploracao_cno.ipynb
│   ├── exploracao_tabela_mestre.ipynb
│   └── tabela_mestre.ipynb   # Versão interativa da construção da tabela mestre
│
├── dados/
│   ├── raw/               # Arquivos manuais de entrada (não versionados)
│   ├── silver/            # Saídas por fonte, prontas para análise (não versionadas)
│   └── gold/              # Tabela mestre — input do modelo (não versionada)
│
└── docs/
    └── dicionario_de_dados.md   # Descrição de todas as fontes e colunas
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

A tabela mestre é salva em `dados/gold/tabela_mestre.xlsx` com ~143 observações mensais e 32 colunas (1 variável alvo + 31 features).

---

## Configuração

Todos os parâmetros ficam em `config.yaml`:

- **`paths`** — caminhos de entrada e saída de cada pipeline
- **`filters`** — intervalo de datas (`date_start` / `date_end`)
- **`api`** — códigos de séries do IPEA, BCB e SIDRA
- **`geo`** — códigos de UF para coleta do SIDRA
- **`sectors`** — seções industriais filtradas no PIM-PF e IPP
- **`anfavea`** — categorias e variáveis do layout do Excel
- **`cno`** — colunas e filtros geográficos do CSV

---

## Documentação

- [`docs/dicionario_de_dados.md`](docs/dicionario_de_dados.md) — descrição detalhada de todas as fontes, colunas e da tabela mestre
