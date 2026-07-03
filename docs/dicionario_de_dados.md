# Dicionário de Dados — Steel Demand Forecast

## Visão Geral

O projeto consolida dados de múltiplas fontes públicas para modelagem de demanda de aço no Brasil. O fluxo segue a arquitetura medallion:

```
dados/raw/ + APIs   →   ETL   →   steeldemand.bronze.*   →   steeldemand.silver.*   →   steeldemand.gold.tabela_mestre
   (staging local)                      (dados crus)              (por fonte)                  (input do modelo)
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
| **Output bronze** | `steeldemand.bronze.anfavea_autoveiculos` |
| **Output silver** | `steeldemand.silver.anfavea_producao_veiculos` |
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
| **Output bronze** | `steeldemand.bronze.cno` |
| **Output silver** | `steeldemand.silver.gov_br_cno` |
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
| **Output bronze** | `steeldemand.bronze.performance_mensal` |
| **Output silver** | `steeldemand.silver.performance` |
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
| **Output bronze** | `steeldemand.bronze.ipea_selic` |
| **Output silver** | `steeldemand.silver.ipea_selic` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `taxa_selic_aa` | float | Taxa SELIC acumulada em 12 meses (% a.a.) |

#### 4b. Formação Bruta de Capital (FBC)

| Atributo | Detalhe |
|---|---|
| **Código IPEA** | `GAC12_INDFBCFDESSAZ12` |
| **Output bronze** | `steeldemand.bronze.ipea_fbc` |
| **Output silver** | `steeldemand.silver.ipea_fbc` |
| **Observação** | Excluído da tabela mestre (série descontinuada) |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `formacao_bruta_capital` | float | Índice de FBC dessazonalizado |

#### 4c. Taxa de Câmbio

| Atributo | Detalhe |
|---|---|
| **Código IPEA** | `GM366_ERC366` |
| **Output bronze** | `steeldemand.bronze.ipea_cambio` |
| **Output silver** | `steeldemand.silver.ipea_cambio` |

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
| **Output bronze** | `steeldemand.bronze.bcb_selic` |
| **Output silver** | `steeldemand.silver.bc_sgs_projecao_selic` |
| **Observação** | Excluído da tabela mestre |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `SELIC` | float | Taxa SELIC diária média do mês (% a.d.) |

#### 5b. IPCA e PIB Mensal

| Atributo | Detalhe |
|---|---|
| **Códigos SGS** | IPCA: `433` / PIB mensal: `4380` |
| **Output bronze** | `steeldemand.bronze.bcb_ipca_pib` |
| **Output silver** | `steeldemand.silver.bc_sgs_ipca_pib` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `IPCA` | float | Variação mensal do IPCA (%) |
| `PIB_mensal` | float | PIB mensal em R$ milhões (preços correntes) |

#### 5c. Operações de Crédito — Indústria

| Atributo | Detalhe |
|---|---|
| **Códigos SGS** | Construção: `22030` / Infraestrutura: `27725` / Metalurgia e siderurgia: `27748` |
| **Output bronze** | `steeldemand.bronze.bcb_credito_industria` |
| **Output silver** | `steeldemand.silver.bc_sgs_operacoes_credito_industria` |

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
| **Output bronze** | `steeldemand.bronze.sidra_sinapi_m2` |
| **Output silver** | `steeldemand.silver.sidra_sinapi_m2` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês de referência |
| `custo_projeto_m2` | float | Custo mediano de construção residencial por m² (R$), soma das UFs |

#### 6b. PIM-PF — Pesquisa Industrial Mensal (Produção Física)

| Atributo | Detalhe |
|---|---|
| **Tabela SIDRA** | `8888` |
| **Variável** | `PIMPF - Número-índice (2022=100)` |
| **Output bronze** | `steeldemand.bronze.sidra_pim_pf` |
| **Output silver** | `steeldemand.silver.sidra_pim_pf` |

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
| **Output bronze** | `steeldemand.bronze.sidra_ipp` |
| **Output silver** | `steeldemand.silver.sidra_ipp` |

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
| **Output bronze** | `steeldemand.bronze.sidra_pnad` |
| **Output silver** | `steeldemand.silver.sidra_pnad_ocupacao` |

| Coluna | Tipo | Descrição |
|---|---|---|
| `Date` | date | Primeiro dia do mês central do trimestre móvel |
| `Nível da ocupação, na semana de referência, das pessoas de 14 anos ou mais de idade` | float | Taxa de ocupação (%) da população de 14+ anos |

---

## Tabela Mestre — steeldemand.gold.tabela_mestre

A tabela mestre é o artefato final do pipeline ETL, gerada por `etl/tabela_mestre.py` consolidando todas as fontes silver. É o input direto do modelo de machine learning.

| Atributo | Detalhe |
|---|---|
| **Output gold** | `steeldemand.gold.tabela_mestre` |
| **Granularidade** | Mensal |
| **Cobertura efetiva** | 2014-03 até presente (limitada pelo menor período comum entre as fontes) |
| **Dimensões** | ~143 observações × 32 colunas |

### Convenção de nomes de coluna

As colunas da tabela mestre seguem `snake_case`, minúsculas, sem acento. O
mapeamento é aplicado por `padronizar_colunas_mestre` (`utils/transforms.py`),
a partir do dicionário `RENOMEIA_COLUNAS_MESTRE` — fonte única de verdade do
rename. Os arquivos silver individuais mantêm os nomes originais das fontes
(ex: `24 METALURGIA`, `Date`); a padronização ocorre só na consolidação gold.

Regras aplicadas:

- Códigos numéricos de classificação (CNAE/SIDRA) são removidos do nome — já
  documentados aqui, não precisam estar na coluna.
- Colunas de PIM-PF e IPP recebem prefixo de fonte (`pim_`, `ipp_`) porque
  descrevem os mesmos setores (metalurgia, máquinas...) com métricas
  diferentes (índice de produção física vs. índice de preço) — sem prefixo
  colidiriam. O mesmo vale para `cno_`, `anfavea_`, `pnad_`.
- Termos recorrentes e autoexplicativos são abreviados de forma fixa:
  `fabricação` → `fab`, `máquinas` → `maq`, `equipamentos` → `equip`,
  `aparelhos` → `apar`, `materiais` → `mat`, `veículos` → `veic`.
- Stopwords (`de`, `da`, `e`, `exceto`...) são descartadas.

### Variável Alvo

| Coluna | Tipo | Fonte | Descrição |
|---|---|---|---|
| `consumo_aparente` | float | Performance (IABr) | Consumo aparente mensal de aços longos no Brasil (mil toneladas) |

### Features

| Coluna | Tipo | Fonte | Coluna original (silver) |
|---|---|---|---|
| `data` | date | — | `Date` |
| `custo_projeto_m2` | float | SIDRA / SINAPI | *(inalterada)* |
| `operacoes_credito_industria_construcao` | float | BCB / SGS | *(inalterada)* |
| `operacoes_credito_industria_infraestrutura` | float | BCB / SGS | *(inalterada)* |
| `operacoes_credito_industria_metalurgia_siderurgia` | float | BCB / SGS | *(inalterada)* |
| `cno_outras_unidades` | float | CNO | `Outra` |
| `cno_km` | float | CNO | `km` |
| `cno_kva` | float | CNO | `kva` |
| `cno_kw` | float | CNO | `kw` |
| `cno_m2` | float | CNO | `m2` |
| `cno_m3` | float | CNO | `m3` |
| `pim_metalurgia` | float | SIDRA / PIM-PF | `3.24 Metalurgia` |
| `pim_fab_maq_equip` | float | SIDRA / PIM-PF | `3.28 Fabricação de máquinas e equipamentos` |
| `pim_fab_veic_reboque_carroceria` | float | SIDRA / PIM-PF | `3.29 Fabricação de veículos automotores, reboques e carrocerias` |
| `pim_fab_outros_equip_transporte` | float | SIDRA / PIM-PF | `3.30 Fabricação de outros equipamentos de transporte, exceto veículos automotores` |
| `ipca` | float | BCB / SGS | `IPCA` |
| `pib_mensal` | float | BCB / SGS | `PIB_mensal` |
| `anfavea_producao_autoveiculos_total` | int | ANFAVEA | `AUTOVEÍCULOS TOTAL_Produção` |
| `anfavea_producao_automoveis` | int | ANFAVEA | `AUTOMÓVEIS_Produção` |
| `anfavea_producao_comerciais_leves` | int | ANFAVEA | `COMERCIAIS LEVES_Produção` |
| `anfavea_producao_caminhoes` | int | ANFAVEA | `CAMINHÕES_Produção` |
| `anfavea_producao_onibus` | int | ANFAVEA | `ÔNIBUS_Produção` |
| `anfavea_producao_total` | int | ANFAVEA | `producao_total` |
| `valor_cambio_reais` | float | IPEA | *(inalterada)* |
| `ipp_metalurgia` | float | SIDRA / IPP | `24 METALURGIA` |
| `ipp_fab_produtos_metal` | float | SIDRA / IPP | `25 FABRICAÇÃO DE PRODUTOS DE METAL, EXCETO MÁQUINAS E EQUIPAMENTOS` |
| `ipp_fab_maq_apar_mat_eletricos` | float | SIDRA / IPP | `27 FABRICAÇÃO DE MÁQUINAS, APARELHOS E MATERIAIS ELÉTRICOS` |
| `ipp_fab_maq_equip` | float | SIDRA / IPP | `28 FABRICAÇÃO DE MÁQUINAS E EQUIPAMENTOS` |
| `ipp_fab_veic_reboque_carroceria` | float | SIDRA / IPP | `29 FABRICAÇÃO DE VEÍCULOS AUTOMOTORES, REBOQUES E CARROCERIAS` |
| `ipp_fab_outros_equip_transporte` | float | SIDRA / IPP | `30 FABRICAÇÃO DE OUTROS EQUIPAMENTOS DE TRANSPORTE, EXCETO VEÍCULOS AUTOMOTORES` |
| `pnad_taxa_ocupacao` | float | SIDRA / PNAD | `Nível da ocupação, na semana de referência, das pessoas de 14 anos ou mais de idade` |
| `taxa_selic_aa` | float | IPEA | *(inalterada)* |

### Arquivos silver excluídos da tabela mestre

| Arquivo | Motivo |
|---|---|
| `performance.xlsx` | É a fonte da variável alvo, não uma feature |
| `ipea_fbc.xlsx` | Série descontinuada |
| `bc_sgs_projecao_selic.xlsx` | Redundante com `taxa_selic_aa` do IPEA |
