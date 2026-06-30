# Dicionário de Dados — Steel Demand Forecast

## Visão Geral

O projeto consolida dados de múltiplas fontes públicas para modelagem de demanda de aço no Brasil. O fluxo segue a arquitetura medallion:

```
dados/raw/   →   ETL   →   dados/silver/   →   tabela_mestre   →   dados/gold/
  (input)                    (por fonte)                           (input do modelo)
```

---

## Fontes de Dados

### 1. ANFAVEA — Produção de Veículos Automotores

| Atributo | Detalhe |
|---|---|
| **Fonte** | Associação Nacional dos Fabricantes de Veículos Automotores |
| **URL** | https://anfavea.com.br/site/edicoes-em-excel/ |
| **Tipo de ingestão** | Arquivo manual (`.xlsx`) |
| **Input** | `dados/raw/anfavea_autoveiculos.xlsx` |
| **Output silver** | `dados/silver/anfavea_producao_veiculos.xlsx` |
| **Granularidade** | Mensal |
| **Cobertura** | 2013-01 até presente |

#### Colunas — silver

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `AUTOVEÍCULOS TOTAL_Produção` | int | Total de autoveículos produzidos |
| `AUTOMÓVEIS_Produção` | int | Automóveis produzidos |
| `COMERCIAIS LEVES_Produção` | int | Comerciais leves produzidos (picapes, vans) |
| `CAMINHÕES_Produção` | int | Caminhões produzidos |
| `ÔNIBUS_Produção` | int | Ônibus produzidos |
| `producao_total` | int | Soma de todas as categorias de produção |

---

### 2. CNO — Cadastro Nacional de Obras

| Atributo | Detalhe |
|---|---|
| **Fonte** | Receita Federal do Brasil |
| **URL** | https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-de-obras-cno |
| **Tipo de ingestão** | Arquivo manual (`.csv`) |
| **Input** | `dados/raw/cno.csv` |
| **Output silver** | `dados/silver/gov_br_cno.xlsx` |
| **Granularidade** | Mensal (agregado da data de início da obra) |
| **Cobertura** | 2013-01 até presente |
| **Filtros aplicados** | Somente obras no Brasil (`Nome do pais = BRASIL`), excluindo exterior (`Estado ≠ EX`) |

#### Colunas — silver

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de início das obras |
| `m2` | float | Área total registrada em metros quadrados |
| `m3` | float | Volume total registrado em metros cúbicos |
| `km` | float | Extensão total registrada em quilômetros |
| `kva` | float | Capacidade total registrada em quilovolt-ampere |
| `kw` | float | Potência total registrada em quilowatts |
| `Outra` | float | Área/volume em outras unidades de medida |

---

### 3. Performance Mensal — Produção e Consumo de Aço

| Atributo | Detalhe |
|---|---|
| **Fonte** | Instituto Aço Brasil (IABr) |
| **URL** | https://acobrasil.org.br/site/estatisticas/ |
| **Tipo de ingestão** | Arquivo manual (`.xls`) |
| **Input** | `dados/raw/Performance-Mensal_<ano.mes>.xls` |
| **Output silver** | `dados/silver/performance.xlsx` |
| **Granularidade** | Mensal |
| **Cobertura** | 2013-01 até presente |

#### Colunas — silver (formato long)

| Coluna | Tipo | Descrição |
|---|---|---|
| `Categoria` | str | Categoria principal (ex: Produção, Consumo Aparente, Exportações) |
| `Especificação` | str | Subcategoria ou tipo de produto (ex: Longos, Planos) |
| `Data` | date | Primeiro dia do mês de referência |
| `Valor` | float | Valor numérico da métrica (unidade varia por especificação, geralmente mil toneladas) |

#### Variável alvo usada no modelo

| Especificação | Categoria |
|---|---|
| `Longos / Long Products (Inclui Blocos e Tarugos / Included Ingots, Blooms and Billets)` | `Consumo Aparente / Apparent Consumption (***)` |

---

### 4. IPEA Data — Indicadores Macroeconômicos

| Atributo | Detalhe |
|---|---|
| **Fonte** | Instituto de Pesquisa Econômica Aplicada |
| **URL** | http://www.ipeadata.gov.br |
| **Biblioteca** | `ipeadatapy` |
| **Tipo de ingestão** | API |

#### 4a. SELIC Anual

| Atributo | Detalhe |
|---|---|
| **Código IPEA** | `PAN12_TJOVER12` |
| **Output silver** | `dados/silver/ipea_selic.xlsx` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `taxa_selic_aa` | float | Taxa SELIC acumulada em 12 meses (% a.a.) |

#### 4b. Formação Bruta de Capital (FBC)

| Atributo | Detalhe |
|---|---|
| **Código IPEA** | `GAC12_INDFBCFDESSAZ12` |
| **Output silver** | `dados/silver/ipea_fbc.xlsx` |
| **Observação** | Excluído da tabela mestre (série descontinuada) |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `formacao_bruta_capital` | float | Índice de FBC dessazonalizado |

#### 4c. Taxa de Câmbio

| Atributo | Detalhe |
|---|---|
| **Código IPEA** | `GM366_ERC366` |
| **Output silver** | `dados/silver/ipea_cambio.xlsx` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `valor_cambio_reais` | float | Taxa de câmbio R$/US$ (média mensal) |

---

### 5. Banco Central do Brasil — SGS

| Atributo | Detalhe |
|---|---|
| **Fonte** | Banco Central do Brasil — Sistema Gerenciador de Séries Temporais |
| **URL** | https://www3.bcb.gov.br/sgspub/ |
| **Biblioteca** | `python-bcb` |
| **Tipo de ingestão** | API |

#### 5a. SELIC Diária (projeção)

| Atributo | Detalhe |
|---|---|
| **Código SGS** | `432` |
| **Output silver** | `dados/silver/bc_sgs_projecao_selic.xlsx` |
| **Observação** | Excluído da tabela mestre |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `SELIC` | float | Taxa SELIC diária média do mês (% a.d.) |

#### 5b. IPCA e PIB Mensal

| Atributo | Detalhe |
|---|---|
| **Códigos SGS** | IPCA: `433` / PIB mensal: `4380` |
| **Output silver** | `dados/silver/bc_sgs_ipca_pib.xlsx` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `IPCA` | float | Variação mensal do IPCA (%) |
| `PIB_mensal` | float | PIB mensal em R$ milhões (preços correntes) |

#### 5c. Operações de Crédito — Indústria

| Atributo | Detalhe |
|---|---|
| **Códigos SGS** | Construção: `22030` / Infraestrutura: `27725` / Metalurgia e siderurgia: `27748` |
| **Output silver** | `dados/silver/bc_sgs_operacoes_credito_industria.xlsx` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `operacoes_credito_industria_construcao` | float | Saldo de crédito para construção civil (R$ milhões) |
| `operacoes_credito_industria_infraestrutura` | float | Saldo de crédito para infraestrutura (R$ milhões) |
| `operacoes_credito_industria_metalurgia_siderurgia` | float | Saldo de crédito para metalurgia e siderurgia (R$ milhões) |

---

### 6. SIDRA/IBGE — Pesquisas Industriais e de Preços

| Atributo | Detalhe |
|---|---|
| **Fonte** | Instituto Brasileiro de Geografia e Estatística |
| **URL** | https://sidra.ibge.gov.br |
| **Biblioteca** | `sidrapy` |
| **Tipo de ingestão** | API |
| **Cobertura geográfica** | Todas as 26 UFs + DF (séries por UF são agregadas nacionalmente) |

#### 6a. SINAPI — Custo por m²

| Atributo | Detalhe |
|---|---|
| **Tabela SIDRA** | `647` |
| **Output silver** | `dados/silver/sidra_sinapi_m2.xlsx` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `custo_projeto_m2` | float | Custo mediano de construção residencial por m² (R$), soma das UFs |

#### 6b. PIM-PF — Pesquisa Industrial Mensal (Produção Física)

| Atributo | Detalhe |
|---|---|
| **Tabela SIDRA** | `8888` |
| **Variável** | `PIMPF - Número-índice (2022=100)` |
| **Output silver** | `dados/silver/sidra_pim_pf.xlsx` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `3.24 Metalurgia` | float | Índice de produção física — metalurgia (base 2022=100) |
| `3.28 Fabricação de máquinas e equipamentos` | float | Índice de produção física — máquinas e equipamentos (base 2022=100) |
| `3.29 Fabricação de veículos automotores, reboques e carrocerias` | float | Índice de produção física — veículos (base 2022=100) |
| `3.30 Fabricação de outros equipamentos de transporte, exceto veículos automotores` | float | Índice de produção física — outros transportes (base 2022=100) |

#### 6c. IPP — Índice de Preços ao Produtor

| Atributo | Detalhe |
|---|---|
| **Tabela SIDRA** | `6903` |
| **Variável** | `IPP - Número-índice (dezembro de 2018 = 100)` |
| **Output silver** | `dados/silver/sidra_ipp.xlsx` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `24 METALURGIA` | float | IPP — metalurgia (base dez/2018=100) |
| `25 FABRICAÇÃO DE PRODUTOS DE METAL, EXCETO MÁQUINAS E EQUIPAMENTOS` | float | IPP — produtos de metal (base dez/2018=100) |
| `27 FABRICAÇÃO DE MÁQUINAS, APARELHOS E MATERIAIS ELÉTRICOS` | float | IPP — máquinas elétricas (base dez/2018=100) |
| `28 FABRICAÇÃO DE MÁQUINAS E EQUIPAMENTOS` | float | IPP — máquinas e equipamentos (base dez/2018=100) |
| `29 FABRICAÇÃO DE VEÍCULOS AUTOMOTORES, REBOQUES E CARROCERIAS` | float | IPP — veículos (base dez/2018=100) |
| `30 FABRICAÇÃO DE OUTROS EQUIPAMENTOS DE TRANSPORTE, EXCETO VEÍCULOS AUTOMOTORES` | float | IPP — outros transportes (base dez/2018=100) |

#### 6d. PNAD Contínua — Nível de Ocupação

| Atributo | Detalhe |
|---|---|
| **Tabela SIDRA** | `6379` |
| **Cobertura** | Brasil (nível nacional) |
| **Output silver** | `dados/silver/sidra_pnad_ocupacao.xlsx` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês central do trimestre móvel |
| `Nível da ocupação, na semana de referência, das pessoas de 14 anos ou mais de idade` | float | Taxa de ocupação (%) da população de 14+ anos |

---

## Tabela Mestre — dados/gold/tabela_mestre.xlsx

A tabela mestre é o artefato final do pipeline ETL, gerada por `etl/tabela_mestre.py` consolidando todas as fontes silver. É o input direto do modelo de machine learning.

| Atributo | Detalhe |
|---|---|
| **Output gold** | `dados/gold/tabela_mestre.xlsx` |
| **Granularidade** | Mensal |
| **Cobertura efetiva** | 2014-03 até presente (limitada pelo menor período comum entre as fontes) |
| **Dimensões** | ~143 observações × 32 colunas |

### Variável Alvo

| Coluna | Tipo | Fonte | Descrição |
|---|---|---|---|
| `Consumo Aparente` | float | Performance (IABr) | Consumo aparente mensal de aços longos no Brasil (mil toneladas) |

### Features

| Coluna | Tipo | Fonte |
|---|---|---|
| `Date` | date | — |
| `custo_projeto_m2` | float | SIDRA / SINAPI |
| `operacoes_credito_industria_construcao` | float | BCB / SGS |
| `operacoes_credito_industria_infraestrutura` | float | BCB / SGS |
| `operacoes_credito_industria_metalurgia_siderurgia` | float | BCB / SGS |
| `Outra` | float | CNO |
| `km` | float | CNO |
| `kva` | float | CNO |
| `kw` | float | CNO |
| `m2` | float | CNO |
| `m3` | float | CNO |
| `3.24 Metalurgia` | float | SIDRA / PIM-PF |
| `3.28 Fabricação de máquinas e equipamentos` | float | SIDRA / PIM-PF |
| `3.29 Fabricação de veículos automotores, reboques e carrocerias` | float | SIDRA / PIM-PF |
| `3.30 Fabricação de outros equipamentos de transporte, exceto veículos automotores` | float | SIDRA / PIM-PF |
| `IPCA` | float | BCB / SGS |
| `PIB_mensal` | float | BCB / SGS |
| `AUTOVEÍCULOS TOTAL_Produção` | int | ANFAVEA |
| `AUTOMÓVEIS_Produção` | int | ANFAVEA |
| `COMERCIAIS LEVES_Produção` | int | ANFAVEA |
| `CAMINHÕES_Produção` | int | ANFAVEA |
| `ÔNIBUS_Produção` | int | ANFAVEA |
| `producao_total` | int | ANFAVEA |
| `valor_cambio_reais` | float | IPEA |
| `24 METALURGIA` | float | SIDRA / IPP |
| `25 FABRICAÇÃO DE PRODUTOS DE METAL, EXCETO MÁQUINAS E EQUIPAMENTOS` | float | SIDRA / IPP |
| `27 FABRICAÇÃO DE MÁQUINAS, APARELHOS E MATERIAIS ELÉTRICOS` | float | SIDRA / IPP |
| `28 FABRICAÇÃO DE MÁQUINAS E EQUIPAMENTOS` | float | SIDRA / IPP |
| `29 FABRICAÇÃO DE VEÍCULOS AUTOMOTORES, REBOQUES E CARROCERIAS` | float | SIDRA / IPP |
| `30 FABRICAÇÃO DE OUTROS EQUIPAMENTOS DE TRANSPORTE, EXCETO VEÍCULOS AUTOMOTORES` | float | SIDRA / IPP |
| `Nível da ocupação, na semana de referência, das pessoas de 14 anos ou mais de idade` | float | SIDRA / PNAD |
| `taxa_selic_aa` | float | IPEA |

### Arquivos silver excluídos da tabela mestre

| Arquivo | Motivo |
|---|---|
| `performance.xlsx` | É a fonte da variável alvo, não uma feature |
| `ipea_fbc.xlsx` | Série descontinuada |
| `bc_sgs_projecao_selic.xlsx` | Redundante com `taxa_selic_aa` do IPEA |
