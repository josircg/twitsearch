# Design Document

_App `core` do Capitu._

> **Natureza deste documento.** Documentação de **engenharia reversa** do design
> atual da app `core`. Descreve como o sistema está construído hoje (arquitetura,
> componentes, dados e fluxos) e aponta decisões implícitas e pontos de atenção.
> Não é a proposta de uma feature nova.

## Overview

A app `core` é o núcleo do Capitu e responde por: modelagem de domínio, coleta de
tweets na API v2 do Twitter/X, importação dos dados coletados para o MySQL, busca
na base local, exportação (CSV/Gephi/nuvem/grafo) e a interface administrativa
mais os endpoints JSON de integração. Este documento descreve o design atual
(engenharia reversa), suas decisões implícitas e pontos de atenção.

O princípio organizador é a separação entre um **plano web** síncrono e um
**plano de coleta** assíncrono, conectados por um **datalake** de arquivos JSON
em `data/`. Isso isola a coleta (limitada por rate limit e sujeita a falhas de
rede) da escrita no banco, e permite reprocessar, importar em lote e manter um
histórico bruto para backup/restore.

## Architecture

A `core` segue a arquitetura padrão de um app Django, com uma separação clara
entre o **plano web** (síncrono, request/response e admin) e o **plano de
coleta/processamento** (assíncrono, via *management commands* disparados por
cron/scheduler). A ponte entre os dois planos é o **datalake** em `data/`:

```
                 ┌─────────────────────────────────────────────┐
                 │                 Plano Web                     │
   Usuário  ───► │  Django Admin (poweradmin) + views + forms    │
   externo       │  endpoints /api/* (integrações)               │
                 └───────────────┬───────────────────────────────┘
                                 │ cria Projeto/Termo/Agendamento
                                 ▼
                           Banco MySQL (ORM)
                                 ▲
                                 │ importa (importjson)
                 ┌───────────────┴───────────────────────────────┐
                 │            Plano de Coleta (cron)              │
   Twitter  ◄──► │  crawler ──► save_result ──► data/*.json        │
   API v2        │  scheduler (backup S3), retweets, enriquecimento│
                 └────────────────────────────────────────────────┘
```

Motivação do datalake intermediário: desacoplar a coleta (limitada por rate
limit e sujeita a falhas de rede) da escrita no banco, permitindo reprocessar os
JSON, importar em lote e manter um histórico bruto para backup/restore.

## Components and Interfaces

### 1. Modelagem de domínio (`models.py`)

Camada de persistência. Define a hierarquia de pesquisa e os dados coletados
(detalhe no "Modelo de dados"). Expõe também lógica de agregação como
`@property` (totais, usuários únicos) e consultas SQL cruas para estatísticas
pesadas (via `connection.cursor()`).

### 2. Interface administrativa (`admin.py` + `forms.py` + `crispy_admin_layout.py`)

- Baseada em `poweradmin.PowerModelAdmin`, que adiciona botões de ação
  (`PowerButton`) e busca múltipla (`multi_search`).
- `ProjetoAdmin` é o centro da UX do usuário externo: inlines de termos, botões
  para Estatísticas, Nuvem, Grafo, Backup, Exclusão de JSON e adição de termo;
  controle de permissão por grupo (`projeto_readonly`).
- Ações em lote vêm de `actions.py` e são injetadas em `get_actions`.
- `ProjetoAdminForm` normaliza o `prefix` e integra com o catálogo do OpenSearch.
- Inlines desabilitam adição/edição direta de termos quando o projeto tem muitos
  termos (>50) por desempenho.

### 3. Views do usuário externo (`views.py`)

Views `@staff`/admin que entregam HTML e arquivos:

- `stats` — estatísticas do projeto (top tweets, gráfico por dia via Plotly, CSV
  de usuários); dispara recomputo de alcance quando os dados estão desatualizados.
- `nuvem` — gera a nuvem de palavras com `wordcloud`, usando máscara opcional.
- `create_graph` / `gerar_gephi` — geram GEXF (NetworkX) e CSV de arestas.
- `solicitar_csv`, `solicita_busca` — disparam tarefas longas em `Thread`.
- `importacao_arquivo` — upload de XLSX/TXT.
- `status_coleta` — gráfico por dia a partir do OpenSearch ou do banco.
- `get_source` — download do JSON bruto de um tweet (de `data/cached/`).

### 4. API JSON (`api.py`)

Endpoints "crus" (sem DRF) que montam dicionários e serializam com
`json.dumps`. A maioria protege o acesso com o header `auth` validado contra
`settings.AUTH_KEYS`. Expõem redes, eixos, projetos, termos, processo e, para o
Telegram, a lista de canais; e permitem à integração ler/gravar o ponteiro de
processamento por termo/rede (`TermoStatus`).

### 5. Coleta (`management/commands/crawler.py`)

Componente mais complexo. A classe `Crawler` encapsula o estado de uma coleta
(limite, ponteiros since/until, menor/maior tweet, menor data). Três estratégias:

- **Padrão**: termo novo, parte do início da carga.
- **Contínua**: termo em andamento (status Ativo), parte do `since_id =
  ult_tweet`.
- **Correção/Recuperação**: termo em Fila/Interrompido, busca a faixa entre o
  último capturado e o primeiro tweet do intervalo (usa `find_first_tweet`).

Funções de orquestração: `processa_termo` (coleta regular) e `processa_agenda`
(agendamento especial). Cada tweet obtido é reidratado com o autor (dos
`includes`) e gravado via `save_result`. Os tweets-pai (de retweets/quotes) vêm
nos `includes` e são gravados sem associação a termo.

### 6. Importação (`management/commands/importjson.py`)

A classe `Processo` implementa `load_twitter(src)`, o coração da importação:
normaliza tanto JSON da API v1 quanto v2, cria/atualiza `TweetUser`,
`FollowersHistory`, `Tweet`, `Retweet` (referências) e `TweetInput`. O `Command`
varre `data/`, importa em transações manuais (`set_autocommit(False)` + `commit`
por arquivo), move arquivos corrompidos para `data/ruim/` e atualiza contadores
de termo/projeto ao final. Reutilizado por `actions.import_xlsx` e
`actions.importa_tweets`.

### 7. Processamento e exportação (`actions.py`)

Agrupa as ações do admin (recalcular estatísticas, finalizar/reativar projeto e
termo, interromper, desassociar tweet) e as rotinas de exportação
(`generate_tags_file`, `export_extra_action`), a busca local (`busca_local`), a
estimativa de volume (`calcula_estimativa`) e os importadores XLSX/lista.

### 8. Integrações externas

- **Twitter/X**: `twitsearch.local.get_api_client()` devolve o cliente tweepy;
  `core/client.py` é uma cópia vendorizada do `Client` do tweepy.
- **OpenSearch** (`opensearch.py`): conexão, criação de índice e indexação de
  documentos; usado opcionalmente (condicionado a `settings.OPENSEARCH_SERVERS`).
- **PostgreSQL** (`apps.connect_postgresql`): fonte externa para algumas rotinas.
- **S3** (via `backup_project`): backup dos JSON.

### 9. Infraestrutura compartilhada (`apps.py`, `__init__.py`)

- `apps.py`: `get_management_logger` (log em arquivo + console), `save_result`
  (grava JSON no datalake), `connect_postgresql`, `find_first_tweet`,
  `alog_message`.
- `__init__.py`: utilitários puros (`intdef`, `convert_date`, `clean_pontuation`,
  `stopwords`, `find_urls`, `log_message`, `check_dir`).

## Data Models

```
Rede ──< Projeto >── Eixo ──> Group
             │  │
             │  └── redes (M2M Rede), lista_canais ──> telegram.Lista
             │
             ├──< Termo ──< Processamento
             │        │        │
             │        │        └──< TweetInput >── Tweet
             │        └──< TermoStatus >── Rede
             │        └──< Agendamento
             │
TweetUser ──< Tweet ──< TweetInput
     │  │        └──< Retweet (tweet original)
     │  └──< FollowersHistory
     └──< Retweet (autor do retweet)
```

Entidades e papéis:

| Modelo            | Papel |
|-------------------|-------|
| `Rede`            | Rede social de origem (Twitter/X, Telegram, YouTube). |
| `Eixo`            | Agrupamento temático de projetos, ligado a um `Group`. |
| `Projeto`         | Unidade central; status A/I/C; totais e stopwords próprias. |
| `Termo`           | Critério de busca; query, período, idioma, tipo, ponteiros. |
| `TermoStatus`     | Status da coleta por (termo, rede) — usado p/ outras redes. |
| `Processamento`   | Execução de rotina (coleta/importação/backup/tags/…). |
| `Agendamento`     | Captura especial pontual (recentes/relevantes/RT/comentários). |
| `TweetUser`       | Autor (PK = id do Twitter). |
| `FollowersHistory`| Histórico de seguidores/seguindo/favoritos por data. |
| `Tweet`           | Tweet (PK = `twit_id`), texto, métricas, idioma, geo. |
| `Retweet`         | Reply (C), Quote (Q) ou Retweet (R); pode preceder o tweet pai. |
| `TweetInput`      | Liga Tweet ao Termo/Processamento que o trouxe (unique tweet+termo). |

Constantes `PROC_*` em `models.py` codificam os tipos de busca/processamento
(ex.: `PROC_FULL`, `PROC_PREMIUM`, `PROC_CONTINUA`, `PROC_RETWEET`,
`PROC_OPENSEARCH`, `PROC_BACKUP`).

## Fluxos principais

### Fluxo de coleta (crawler → datalake → importjson → banco)

1. `crawler` seleciona termos ativos/em fila de projetos ativos (Twitter/X).
2. Para cada termo, `processa_termo` instancia `Crawler`, escolhe a estratégia
   (padrão/contínua/correção) e chama `search_recent` → `search`.
3. `search` pagina a API v2 (`search_all_tweets`/`search_recent_tweets`) até o
   limite, grava cada tweet como JSON (`save_result`) em `data/` e `data/queue/`.
4. Ao final, atualiza `ult_tweet`/`ult_processamento`; se atingiu o limite, marca
   termo como Fila e agenda continuação; se chegou ao fim do período, Concluído.
5. `importjson data` varre `data/`, chama `load_twitter` por registro, grava no
   MySQL, remove os JSON importados e atualiza `last_count`/totais.

### Fluxo de exportação

1. Usuário clica em "Solicitar CSV" → `solicitar_csv` dispara `generate_tags_file`
   em thread.
2. A rotina gera `tags-<id>.csv` e `full-<id>.csv`, zipa, registra um
   `Processamento` do tipo `PROC_TAGS` como Concluído.
3. A tela de estatísticas passa a exibir o botão de download.

### Fluxo de busca local

1. Usuário solicita busca em termo Busca Global/Filtro no Projeto.
2. `busca_local` percorre os tweets candidatos aplicando inclusões/exclusões e
   cria `TweetInput` para os que casam; marca o termo como Concluído.

## Decisões de design implícitas

- **Datalake baseado em arquivos** em vez de escrever direto no banco: favorece
  reprocessamento, backup e tolerância a falhas de rede, ao custo de I/O de disco
  e de uma etapa de importação separada.
- **Transações manuais na importação** (`set_autocommit(False)`, commit por
  arquivo): limita o tamanho das transações e permite isolar arquivos ruins.
- **Admin como interface principal**: reduz código de UI; o poweradmin provê
  botões/ações. Formulários customizados só para o usuário externo.
- **Status como string de 1 caractere** em todos os modelos: compacto, porém
  exige as tabelas de choices para legibilidade.
- **Idempotência via `get_or_create`/`max(...)`** na importação: reimportar o
  mesmo JSON não duplica registros e preserva as maiores métricas.

## Correctness Properties

Invariantes que o design atual pretende preservar (observadas no código; algumas
sem garantia formal — ver Pontos de atenção):

1. **Idempotência da importação.** Reimportar o mesmo JSON não cria `Tweet`,
   `TweetUser`, `Retweet` ou `TweetInput` duplicados — a identidade é a PK do
   Twitter e `TweetInput` tem `unique_together (tweet, termo)`. Métricas são
   atualizadas por `max(...)`, nunca decrementadas.
2. **Associação respeita o escopo do termo.** Um tweet só é ligado a um termo se
   sua data estiver dentro de `[dtinicio, dtfinal]` e seu idioma casar com o
   idioma do termo (quando definido). Fora disso, é gravado sem associação.
3. **Continuidade sem lacunas.** Os ponteiros `ult_tweet` (since) e os
   `Processamento` do tipo `PROC_CONTINUA` garantem que a próxima coleta retome
   de onde a anterior parou, mesmo após atingir o limite ou falhar.
4. **Monotonicidade dos ponteiros.** `ult_tweet` só avança
   (`max(ult_tweet, ultimo_tweet)`), evitando recoletar faixas já processadas.
5. **Terminação da coleta.** Um termo chega a `Concluído` quando a coleta
   ultrapassa a data final (ou inicial, na correção) programada, ou quando nenhum
   registro é encontrado no intervalo.
6. **Transição de status previsível.** Falha de rede do Twitter leva o termo a
   `Interrompido` (recuperável); erro de aplicação leva a `Erro`. Termos travados
   em `Processando` há mais de 1 hora são reativados ao fim do crawler.

## Error Handling

- **Coleta (`crawler`).** `processa_termo`/`processa_agenda` capturam
  `BadRequest` e `TwitterServerError`/`ConnectionResetError` (falha do Twitter →
  status `Interrompido`/agendamento mantido) separadamente de `Exception` genérica
  (erro de aplicação → status `Erro`, com `traceback` no log). Em ambos os casos,
  o `Processamento` é fechado com os contadores no bloco `finally`, e um
  `PROC_CONTINUA` é agendado a partir do menor tweet para permitir retomada.
- **Importação (`importjson`).** Transações manuais com `commit` por arquivo;
  arquivo corrompido é movido para `data/ruim/` e a transação sofre `rollback`.
  Após 10 erros a varredura é interrompida e o processo marcado como `Erro`.
  Arquivo vazio é removido; nenhum arquivo processado remove o `Processamento`
  recém-criado.
- **Rate limit.** O cliente tweepy opera com `wait_on_rate_limit` conforme a
  configuração em `local.py`; o crawler ainda intercala `time.sleep(2)` entre
  termos.
- **Web/UX.** As views usam `get_object_or_404` e reportam falhas via
  `django.contrib.messages` (ex.: backup não concluído, nenhuma palavra para a
  nuvem, tipo de busca inválido). `get_source` retorna 404 quando o JSON bruto não
  existe.
- **Tarefas em `Thread`.** `import_xlsx`/`importacao_arquivo` capturam exceção e
  formatam o traceback; demais threads (`busca_local`, `generate_tags_file`)
  logam o erro, mas não têm retentativa — ver Pontos de atenção.

## Testing Strategy

> Estado atual: a `core` não possui testes automatizados relevantes
> (`core/tests.py` praticamente vazio). Esta seção descreve a estratégia
> recomendada, viabilizada pelo `NoDbTestRunner` já existente em `tests/`.

- **Unitários sem banco (`SimpleTestCase` + `NoDbTestRunner`).** Priorizar as
  funções puras e a lógica de parsing: `core.__init__` (`intdef`, `convert_date`,
  `clean_pontuation`, `find_urls`) e a normalização de `Processo.load_twitter`
  com fixtures de JSON das APIs v1 e v2 (mockando o ORM onde necessário).
- **Unitários com banco.** Cobrir as invariantes de Correctness Properties:
  idempotência da importação, respeito ao escopo do termo (data/idioma) e as
  transições de status do `Termo`.
- **Estratégias do `Crawler`.** Testar a seleção padrão/contínua/correção com o
  cliente tweepy mockado, verificando os ponteiros since/until calculados e a
  terminação por data final/inicial.
- **Views e ações.** Testar `finalizar_projeto_action` (regressão do bug de
  `tot_twits`), `busca_local` (inclusão/exclusão por `-termo`) e os endpoints da
  API (validação de `AUTH_KEYS` e respostas 403).
- **Regressões.** Cada bug corrigido deve ganhar um teste (ex.: `render` em
  `ProjetoAdmin.visao`, `tot_twits` como property).

## Pontos de atenção (design)

> Ver também a lista de "Pontos de atenção" em `requirements.md`. Aqui, os de
> natureza arquitetural.

1. **Acoplamento ao MySQL** via SQL cru com funções específicas do dialeto
   dificulta portabilidade e testes. Considerar camada de repositório ou ORM.
2. **Tarefas longas em `Thread`** dentro do processo web não sobrevivem a
   restart e não têm observabilidade. Uma fila de tarefas (Celery/RQ) traria
   retentativa, visibilidade e isolamento.
3. **`core/client.py` vendorizado** cria dívida de manutenção frente ao tweepy
   upstream. Confirmar se há customização real; caso não, remover.
4. **IDs/nomes de rede hardcoded** (`rede_id == 4`, `nome='Twitter/X'`) tornam o
   sistema frágil a mudanças de cadastro. Referenciar por slug/choice.
5. **Endpoint de escrita sem auth** (`processo_rede_set`, `@csrf_exempt`): risco
   de segurança se exposto.
6. **`scheduler` subutilizado**: hoje só faz backup; o resto da orquestração está
   implícito no agendamento externo do `crawler`/`importjson`. Documentar o
   agendamento real (crontab) seria valioso.
7. **Cobertura de testes ausente**: a lógica mais crítica (`load_twitter`,
   estratégias do `Crawler`) não tem testes; mudanças são arriscadas. O projeto
   já tem o `NoDbTestRunner` em `tests/`, facilitando testes com mocks.
8. **Código morto/comentado** (heatmap em `views.stats`, blocos comentados no
   crawler/admin) polui a leitura e esconde intenção. *(A `view.visao` placeholder
   e sua rota pública já foram removidas; a correção do `render` em
   `ProjetoAdmin.visao` já foi aplicada.)*
