# Estrutura do Projeto — Capitu

Este documento descreve a organização de diretórios e a responsabilidade de cada
parte do código do projeto Capitu. Serve como mapa para localizar onde implementar
ou alterar funcionalidades.

## Visão geral

Capitu é um projeto Django (4.2.x, Python 3.12) de captura de dados de redes
sociais (Twitter/X, Telegram e YouTube). A administração é feita quase
inteiramente pelo Django Admin (com `admin_tools` e `poweradmin`); apenas os
fluxos voltados ao usuário externo usam views e formulários customizados.

A coleta de dados roda fora do ciclo request/response, via *management commands*
executados por agendadores (cron/scheduler). Os dados coletados são persistidos
no banco relacional e também gravados como arquivos JSON no diretório `data/`,
que funciona como *datalake* / fila de processamento.

O banco de dados padrão é **MySQL**, configurado em `twitsearch/local.py` na
variável `DATABASES`. Algumas rotinas específicas usam **PostgreSQL** como fonte
externa de dados (via `connect_postgresql` em `core/apps.py`, lendo
`settings.PG_SERVERS`).

## Raiz do projeto

```
twitsearch/
├── manage.py                 # Entrypoint Django (settings: twitsearch.settings)
├── requirements.txt          # Dependências de produção
├── req-dev.txt               # Dependências de desenvolvimento
├── dashboard.py              # CustomIndexDashboard do admin_tools
├── menu.py                   # CustomMenu do admin_tools
├── fabfile.py                # Tarefas de deploy (Fabric)
├── excecoes.txt              # Stopwords usadas em nuvem de palavras / agrupamento
├── README.md                 # Histórico de versões e roadmap
├── twitsearch/               # Pacote de configuração do projeto Django
├── core/                     # App principal (Twitter/X, projetos, processamento)
├── telegram/                 # App de coleta de canais do Telegram
├── utils/                    # App utilitário (admin helpers, e-mail)
├── templates/                # Templates globais do projeto
├── data/                     # Datalake / fila de JSONs coletados
├── media/                    # Arquivos gerados para o usuário (CSV, nuvens, grafos)
├── logs/                     # Logs das rotinas de management
├── doc/                      # Documentação de instalação e exemplos
└── .kiro/steering/           # Arquivos de steering (contexto para o agente)
```

Notebooks (`*.ipynb`), `twitest.py`, `teste_log.py` e similares na raiz são
scripts de exploração/experimentação, não fazem parte do fluxo de produção.

## `twitsearch/` — configuração do projeto

```
twitsearch/
├── settings.py        # Settings base (INSTALLED_APPS, i18n pt-BR, admin_tools)
├── local.py           # Secrets e config por máquina — NÃO versionado
├── credentials.yaml   # Credenciais de API — NÃO versionar
├── urls.py            # URLconf raiz (admin, admin_tools, include core.urls)
└── wsgi.py            # Entrypoint WSGI (gunicorn em produção)
```

- `settings.py` define o fuso `America/Sao_Paulo`, idioma `pt-BR`, formatos de
  data `dd/mm/aaaa` e separadores decimais brasileiros. Apps de terceiros
  relevantes: `admin_tools`, `poweradmin`, `crispy_forms`, `django_select2`,
  `smart_selects`.
- `local.py` é importado pelo código (ex.: `from twitsearch.local import get_api_client`).
  Contém secrets, a função `get_api_client()`, a variável `DATABASES` (MySQL) e
  configs específicas da máquina (ex.: `PG_SERVERS`). Nunca commitar.
- O banco padrão (MySQL) é definido em `local.py` via `DATABASES`. O `settings.py`
  versionado traz apenas um `DATABASES` SQLite como placeholder; a configuração
  real vem de `local.py`.

## `core/` — app principal

App central que concentra a modelagem de domínio, a coleta do Twitter/X e o
processamento/exportação dos dados.

```
core/
├── models.py              # Modelos de domínio (ver seção "Modelo de domínio")
├── admin.py               # Registro e customização do Django Admin
├── crispy_admin_layout.py # Layouts crispy usados no admin
├── forms.py               # Formulários (admin e usuário externo)
├── views.py               # Views do usuário externo (index, stats, nuvem, grafo…)
├── urls.py                # URLconf do app (views + endpoints /api/)
├── api.py                 # Endpoints JSON consumidos pelo front (redes, termos…)
├── actions.py             # Actions do admin (operações em lote)
├── client.py              # Cliente de acesso à API do Twitter/X
├── opensearch.py          # Integração com OpenSearch/Elasticsearch
├── apps.py                # AppConfig + helpers (logging, postgres, save_result…)
├── __init__.py            # Utilitários puros (intdef, convert_date, stopwords…)
├── templatetags/          # Template tags/filters customizados
├── static/core/           # Assets do app (css, js, img; inclui sigma.js p/ grafos)
├── migrations/            # Migrations (0001…; estado atual do schema)
└── management/commands/   # Rotinas de coleta e processamento (ver abaixo)
```

### `core/apps.py`

Além do `CoreConfig`, hospeda funções de infraestrutura reutilizadas pelas
rotinas: `get_management_logger` (logging com arquivo em `logs/` + console),
`connect_postgresql` (conexões a servidores externos via `settings.PG_SERVERS`),
`save_result` (grava o JSON do tweet em `data/` e em `data/queue/`),
`find_first_tweet` e `alog_message` (log assíncrono no `LogEntry` do admin).

### `core/__init__.py`

Funções utilitárias sem dependência de estado: `intdef`, `clean_pontuation`,
`stopwords` (lê `excecoes.txt`), `find_urls`, `convert_date` (parse do formato
de data do Twitter), `check_dir`, `log_message` (grava no `LogEntry` do admin) e
`OSRun`.

### `core/management/commands/` — rotinas de coleta e processamento

Toda a captura e o processamento pesado roda aqui (executado por cron/scheduler,
não pelo request web). Comandos principais:

- `scheduler.py` — orquestra/agenda a execução das rotinas de coleta.
- `crawler.py` — coleta de tweets a partir dos termos de busca.
- `retweets.py` — coleta de retweets dos tweets já capturados.
- `importjson.py` — importa os JSONs pendentes de `data/` para o banco (também
  faz o restore de backup com `--restore`).
- `export_datalake.py` — exporta os dados coletados.
- `backup_project.py` — backup do projeto (JSON / S3).
- `generate_tags.py` — gera CSV de TAGs para exportação (ex.: Gephi).
- `getgeo.py`, `getlang.py`, `getuserinfo.py` — enriquecimento (geo, idioma, usuário).
- `import_projects.py`, `read_userlist.py` — importação de projetos / listas de usuários.
- `remove_json.py`, `remove_unrelated.py`, `revive_stalled.py`,
  `verifica_integridade.py`, `opensearch_fix.py` — manutenção e correção de base.
- `test_*.py`, `twitter_test.py` — scripts de teste manual de integrações
  (Postgres, S3, OpenSearch, streaming, RapidAPI, retweet).

## `telegram/` — app de coleta do Telegram

```
telegram/
├── models.py              # Categoria, Canal, APIKeys, Lista
├── admin.py               # Admin dos modelos do Telegram
├── forms.py               # Formulários de importação de canais
├── views.py               # importacao_canais (usada por core.urls)
├── templates/             # Templates específicos do app
└── management/commands/
    ├── sync_channels.py   # Sincroniza metadados dos canais
    ├── get_messages.py    # Coleta mensagens dos canais
    └── export_telegram.py # Exporta mensagens coletadas
```

Usa `telethon` para acessar a API do Telegram. As credenciais de API ficam no
modelo `APIKeys`. O arquivo de sessão `sync_channels.session` (raiz) é gerado
pelo telethon.

## `utils/` — app utilitário

```
utils/
├── admin.py   # Helpers e mixins para o Django Admin
├── apps.py    # UtilsConfig
└── email.py   # Envio de e-mail
```

## `templates/` — templates globais

```
templates/
├── base.html, base_site.html, base_form.html, base_mensagem.html
├── home.html
├── 404.html, 500.html
├── admin/     # Overrides do admin (admin_tools/poweradmin)
├── core/      # Telas do usuário externo (stats, importação, status de coleta)
└── nuvem/     # Templates da nuvem de palavras
```

Configurados via `TEMPLATES['DIRS']` em `settings.py`; carregamento combina
`filesystem`, `app_directories` e `admin_tools`.

## `data/` — datalake e fila de processamento

- `data/*.json` — tweets coletados, nomeados como `{tweet_id}_{termo_id}.json`.
- `data/queue/` — JSONs aguardando importação para o banco (`importjson`).
- `data/cached/`, `data/history/`, `data/erro/`, `data/ruim/` — estágios
  intermediários e arquivos com erro.
- `data/media/` — mídia associada.

`save_result` (em `core/apps.py`) grava simultaneamente em `data/` (histórico) e
`data/queue/` (fila a importar).

## `media/` — saídas para o usuário

Arquivos gerados sob demanda e servidos via `MEDIA_URL`: CSVs exportados, imagens
de nuvem de palavras e arquivos de grafo (Gephi/GEXF).

## Modelo de domínio (`core/models.py`)

Hierarquia principal da coleta:

- **`Rede`** — rede social de origem (Twitter, Telegram, YouTube).
- **`Eixo`** — agrupamento temático de projetos, ligado a um `Group` do Django.
- **`Projeto`** (verbose: "Monitoramento") — unidade central. Reúne termos de
  busca, redes, idioma default, estatísticas (`tot_twits`, `alcance`), stopwords
  próprias e status (Ativo/Interrompido/Concluído). Dono é um `User`.
- **`Termo`** — critério de busca dentro de um projeto: query (`busca`), período
  (`dtinicio`/`dtfinal`), idioma, tipo de busca e status da coleta. Guarda
  ponteiros de continuidade (`prim_tweet`, `ult_tweet`, `ult_processamento`).
- **`TermoStatus`** — status da coleta por (termo, rede), para controlar cargas
  de redes diferentes do mesmo termo.
- **`Processamento`** — registro de uma execução de rotina (tipo, data, status,
  total de registros) associada a um termo.
- **`Agendamento`** — agendamentos especiais de captura (mais recentes,
  relevantes, retweets, comentários), com janelas e limites.

Dados coletados:

- **`TweetUser`** — autor (PK = id do Twitter), com `FollowersHistory` para
  evolução de seguidores.
- **`Tweet`** — tweet (PK = `twit_id`), com texto, métricas e idioma.
- **`Retweet`** — reply, quote ou retweet; pode existir antes do tweet original
  (associação feita posteriormente por rotina).
- **`TweetInput`** — liga um `Tweet` ao `Termo`/`Processamento` que o trouxe
  (unique por tweet+termo); controla o flag `exported`.

Os tipos de processamento/busca são constantes `PROC_*` no topo de `models.py`
(ex.: `PROC_FULL`, `PROC_PREMIUM`, `PROC_OPENSEARCH`, `PROC_RETWEET`).

Modelos do Telegram (`telegram/models.py`): **`Categoria`**, **`Canal`**
(com `Status`), **`APIKeys`** (credenciais telethon) e **`Lista`** (coleção de
canais, pública ou privada). `Projeto.lista_canais` referencia uma `Lista`.

## Convenções de organização

- Cada rede social é um app Django separado (`core` para Twitter/X, `telegram`
  para Telegram). Novas integrações (ex.: YouTube) devem seguir o mesmo padrão:
  app próprio com `models`, `admin`, `management/commands` e views/forms só se
  houver interface de usuário externo.
- Coleta e processamento pesado vivem em `management/commands`, nunca em views.
- Operações sobre dados já capturados tendem a ser `actions` do admin
  (`core/actions.py`) ou management commands.
- Arquivos não versionados (secrets/config por máquina): `twitsearch/local.py`,
  `twitsearch/credentials.yaml`, além de `db.sqlite3`, `logs/`, `data/`, `media/`.
