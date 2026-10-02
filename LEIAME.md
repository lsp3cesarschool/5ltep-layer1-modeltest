# 5LTEP-L1 · Benchmark de modelos

[![Tests](https://github.com/lsp3cesarschool/5ltep-layer1-modeltest/actions/workflows/tests.yml/badge.svg)](https://github.com/lsp3cesarschool/5ltep-layer1-modeltest/actions/workflows/tests.yml) [![modelo recomendado](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Flsp3cesarschool%2F5ltep-layer1-modeltest%2Fmain%2Fresults%2Fstatus.pt.json)](results/recommendation.json) [![Licença: MIT](https://img.shields.io/badge/Licen%C3%A7a-MIT-blue.svg)](LICENSE)

[English](README.md) · **Português**

**Qual LLM local transforma melhor um dicionário de dados em PDF numa lista de campos, num runner de
CPU gratuito?** Este repositório mede isso todo mês para o
[5ltep-layer1](https://github.com/lsp3cesarschool/5ltep-layer1) (Camada 1 da pirâmide 5L-TEP) e publica
o modelo que as instâncias usam.

> **Situação: demonstração de pesquisa**, parte de um projeto de mestrado, mantida pelo autor.

## O que os modelos precisam fazer

Muitos portais de dados abertos publicam seus dicionários de dados só em PDF. A Camada 1 os lê em três
etapas: um leitor determinístico de tabelas, depois um LLM local para os PDFs que ele não consegue ler,
depois pessoas para o que não for confirmado. Este benchmark trata da segunda etapa: dado o texto de um
dicionário em PDF, devolver todos os campos com o nome exatamente como escrito, o tipo e o tamanho
declarados. O prompt, o esquema JSON, a temperatura (0), a semente, o tamanho de contexto e a leitura da
resposta são o **código de produção** (`src/pdf_extract.py` do 5ltep-layer1), importado, não copiado.

## Ranking

<!-- LEADERBOARD:START -->
*Atualizado em 2026-10-02 13:50 UTC · 30 casos no gabarito (12 reais, 18 sintéticos) · código de produção em `48f8c47`*

**Recomendação:** llama3.1:8b supera qwen3:8b em +0,065 de F1 dos nomes (IC 95% pareado [-0,003, +0,164]), o que não basta para trocar.

| # | Modelo | Estágio | F1 dos nomes [IC 95%] | EM | LS | Tipos | Válidas | Latência p50 / p90 (s) | PDFs/h | Situação |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | llama3.1:8b | confirm | **0,99** [0,98, 1,00] | 0,99 | 1,00 | 1,00 | 100% | 146 / 403 | 16,5 | elegível |
| 2 | ministral-3:8b | confirm | **0,99** [0,97, 1,00] | 0,99 | 0,99 | 0,99 | 100% | 196 / 480 | 14,1 | elegível |
| 3 | gemma3:12b | confirm | **0,95** [0,88, 1,00] | 0,95 | 0,97 | 1,00 | 100% | 277 / 670 | 9,3 | elegível |
| 4 | qwen3:8b | confirm | **0,93** [0,83, 0,99] | 0,93 | 0,95 | 1,00 | 100% | 228 / 608 | 11,7 | elegível |
| 5 | gemma3:4b | triage | **0,97** [0,94, 0,99] | 0,97 | 1,00 | 1,00 | 100% | 54 / 128 | 52,3 | só triagem |
| 6 | qwen3:1.7b | triage | **0,91** [0,80, 0,99] | 0,89 | 0,95 | 0,97 | 100% | 30 / 107 | 66,4 | só triagem |
| 7 | qwen3:4b-q4_K_M | triage | **0,90** [0,73, 1,00] | 0,90 | 0,93 | 0,99 | 100% | 69 / 217 | 32,6 | só triagem |
| 8 | granite4:3b | triage | **0,84** [0,67, 0,97] | 0,80 | 0,93 | 0,95 | 100% | 63 / 230 | 31,8 | só triagem |
| 9 | qwen3.5:0.8b | triage | **0,82** [0,63, 0,96] | 0,78 | 0,87 | 0,88 | 100% | 23 / 56 | 95,1 | só triagem |
| 10 | qwen3:4b | triage | **0,82** [0,58, 0,99] | 0,82 | 0,89 | 0,98 | 100% | 37 / 121 | 57,8 | só triagem |
| 11 | phi4-mini:3.8b | triage | **0,77** [0,57, 0,93] | 0,75 | 0,85 | 0,96 | 100% | 63 / 197 | 37,3 | só triagem |
| – | *etapa determinística (sem modelo, referência)* | | 0,56 | 0,56 | | | | | | |

**F1 médio dos nomes por layout**

| Model | real/portal | synthetic/list | synthetic/prose | synthetic/table-reordered |
|---|---|---|---|---|
| llama3.1:8b (confirm) | 1,00 | 1,00 | 1,00 | 0,95 |
| ministral-3:8b (confirm) | 1,00 | 1,00 | 1,00 | 0,95 |
| gemma3:12b (confirm) | 1,00 | 1,00 | 1,00 | 0,77 |
| qwen3:8b (confirm) | 1,00 | 1,00 | 1,00 | 0,63 |
| gemma3:4b (triage) | 1,00 | 0,96 | 0,97 | 0,93 |
| qwen3:1.7b (triage) | 1,00 | 0,97 | 1,00 | 0,69 |
| qwen3:4b-q4_K_M (triage) | 1,00 | 1,00 | 1,00 | 0,60 |
| granite4:3b (triage) | 0,92 | 0,67 | 1,00 | 0,78 |
| qwen3.5:0.8b (triage) | 0,57 | 0,99 | 1,00 | 0,71 |
| qwen3:4b (triage) | 1,00 | 0,67 | 1,00 | 0,60 |
| phi4-mini:3.8b (triage) | 0,97 | 0,93 | 0,42 | 0,74 |
| *etapa determinística (sem modelo, referência)* | 1,00 | 0,00 | 0,00 | 0,81 |
<!-- LEADERBOARD:END -->

## Por que um benchmark separado

O modelo roda no runner gratuito do GitHub Actions (4 vCPU, 16 GB, sem GPU), então precisa ser pequeno
e rápido o bastante, e ler um dicionário é uma tarefa diferente de conversar ou do juiz da Camada 3
([5ltep-layer3-modeltest](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest)). Escolher por
rankings gerais não basta: é preciso medir **nesta tarefa, com este prompt, neste hardware**, e de novo
a cada modelo ou versão de prompt nova.

## Como funciona

```
discover ─► triagem (todos, amostra) ─► seleção ─► confirmação (finalistas + produção, todos os casos, fatias) ─► score
 biblioteca  12 casos estratificados     3 melhores   gabarito inteiro, dividido em jobs que cabem no runner          F1 dos nomes + IC,
 do Ollama                                                                                                             orçamento, regra de troca
```

1. **Descoberta** de tags novas das famílias acompanhadas e dos modelos mais novos da biblioteca do
   Ollama (1–9 GB), como no benchmark da Camada 3.
2. **Triagem:** todos os candidatos leem uma amostra fixa e estratificada do gabarito.
3. **Seleção:** os melhores finalistas da triagem, mais o modelo de produção (para uma comparação pareada).
4. **Confirmação:** os finalistas leem o gabarito inteiro, dividido em fatias para que um modelo lento
   ainda caiba no limite de tempo do runner.
5. **Score:** métricas, elegibilidade, recomendação e a tabela deste LEIAME (e do `README.md`).

Os resultados ficam em cache por versão do modelo (digest do manifesto do Ollama), código de produção,
gabarito e estágio: um candidato só roda de novo quando algum deles muda.

## Gabarito

[`gold/cases.json`](gold/cases.json), montado por [`gold/build_gold.py`](gold/build_gold.py) a partir
dos **resultados públicos das instâncias da Camada 1** (IBAMA, ANEEL, Recife), fixados nos seus commits.
Cada caso tem uma lista de campos conhecida por construção:

| Tipo | Como é montado |
|---|---|
| real | um dicionário em PDF publicado por um portal cuja extração determinística o próprio cabeçalho do arquivo confirmou por inteiro: duas fontes independentes concordam em todos os nomes |
| sintético | um esquema que um portal declara num dicionário legível por máquina, renderizado como PDF num layout mais difícil ([`gold/layouts.py`](gold/layouts.py)): texto corrido, lista com marcadores ou tabela com colunas reordenadas |

Os casos reais são, por construção, PDFs cujas tabelas a etapa determinística já lê: medem a fidelidade
com que um modelo copia nomes de documentos reais. Os sintéticos medem os layouts em que o LLM é de fato
necessário. A etapa determinística é avaliada nos mesmos casos, como referência. Fontes e licenças dos
PDFs: [`gold/SOURCES.md`](gold/SOURCES.md).

## Métricas e recomendação

| Métrica | Significado |
|---|---|
| F1 dos nomes [IC 95%] | principal: média harmônica de revocação e precisão dos nomes (maiúsculas e acentos ignorados), média sobre os casos; IC por bootstrap |
| EM, LS | correspondência exata e similaridade de Levenshtein dos nomes (Al Hilmi et al., 2026) |
| tipos | fração dos campos encontrados cujo tipo declarado corresponde ao tipo do Table Schema no gabarito |
| válidas | fração das respostas com pelo menos um campo e sem erro |
| latência, PDFs/h | custo no runner gratuito |

Um finalista é **elegível** com ≥ 90% de respostas válidas e ≥ 90% de cobertura, latência p90 dentro do
tempo limite de produção e dentro do **orçamento mensal**: o tempo médio por PDF vezes os PDFs esperados
por mês precisa caber nas horas de runner definidas em [`candidates.json`](candidates.json). O modelo
**recomendado** é o elegível com maior F1 dos nomes. Uma **troca** em relação à produção exige ganho de
pelo menos 0,03 no F1 dos nomes, com IC 95% pareado por bootstrap acima de zero, e uma versão vista pela
primeira vez há pelo menos 30 dias (uma versão nova tem tempo de ser examinada por outros antes de ser adotada).

## Como as instâncias da Camada 1 o usam

Nenhum token cruza repositórios: cada instância lê o
[`results/recommendation.json`](results/recommendation.json) público no início da etapa do LLM
(`LLM_MODEL=auto`) e usa o campo `use`. Até este benchmark publicar, usam `qwen3:8b`. Cada extração
registra o modelo e o digest que a produziram; um modelo novo não refaz extrações antigas.

## Custo

Repositórios públicos rodam nos runners padrão do GitHub sem custo. Um modelo grande pode levar vários
minutos por PDF em CPU; por isso o gabarito inteiro só roda para os finalistas, e em fatias.

## Reproduzindo

```bash
pip install -r requirements.txt -r ../5ltep-layer1/requirements.txt
UPSTREAM=../5ltep-layer1 python gold/build_gold.py
UPSTREAM=../5ltep-layer1 pytest tests/ -v
```

As execuções que valem são as do GitHub Actions (*Actions → Model benchmark → Run workflow*); o gabarito
é remontado em *Actions → Build gold*.

## Licenças

MIT para o código ([LICENSE](LICENSE)). Os PDFs reais em `gold/pdfs/` são cópias de documentos que os
portais publicam sob licenças abertas (ver `gold/SOURCES.md`); os modelos são usados sob as suas
próprias licenças.
