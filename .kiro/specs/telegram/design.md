# Design Document

_App `telegram` do Capitu._

> **Natureza deste documento.** Documentação de **engenharia reversa** do design
> atual da app `telegram`. Descreve como o sistema está construído hoje e aponta
> decisões implícitas e pontos de atenção. Não é a proposta de uma feature nova.

## Overview

A app `telegram` coleta dados de canais do Telegram e os entrega a um datalake em
PostgreSQL, espelhando o fluxo do Twitter da `core` com uma diferença de destino:
enquanto o Twitter é importado para o MySQL da Capitu, as mensagens do Telegram
são exportadas para uma base PostgreSQL externa consumida por uma pipeline (Mage).

O ciclo tem quatro etapas: **cadastro** dos canais (admin/importação) →
**sincronização** de metadados (`sync_channels`) → **coleta incremental** de
mensagens (`get_messages`, grava JSON em `data/telegram/`) → **exportação** para
o datalake (`export_telegram`). A coleta é assíncrona (`telethon` + `asyncio`) e
reutiliza infraestrutura da `core` (logging, PostgreSQL, `alog_message`).

## Architecture

```
  Admin / Importação CSV-XLSX
        │ cadastra Canal / Lista / Categoria / APIKeys
        ▼
   Banco MySQL (Capitu)
        │
        │  sync_channels (telethon)   get_messages (telethon, async)
        ▼        │                          │
   Canal.id_numerico,         data/telegram/*.json  (lotes incrementais)
   access_hash, metadados             │
                                       │ export_telegram
                                       ▼
                     PostgreSQL datalake (tabelas: telegram, historico, fila_telegram)
                                       │
                                       ▼
                              Pipeline externa (Mage)
```

Pontos de ligação com a `core`:

- A rede "Telegram" participa dos `Projeto` via M2M `redes`; `Projeto.lista_canais`
  aponta para uma `telegram.Lista`.
- O progresso da coleta por termo é registrado em `core.TermoStatus`
  (`rede_id = 4`), exposto no admin desta app.
- A API JSON da `core` (`/api/termos/<rede>`, `/api/canais_telegram/`,
  `/api/get_processo`, `/api/update_processo`) é o contrato que um coletor externo
  usa para saber quais canais processar e reportar progresso.

## Components and Interfaces

### 1. Modelagem (`models.py`)

- `Categoria` — rótulo temático; `tot_canais` como property.
- `Canal` — entidade central; username único, id numérico/access_hash para a API,
  métricas (participantes, mensagens), ponteiro `ultima_mensagem`, `dt_ultima_carga`
  e `status` (Ativo/Processando/Não existe/Inativo).
- `APIKeys` — credenciais `telethon` por usuário (api_id, api_hash, telefone,
  status Ativo/Lotada/Inválida).
- `Lista` — coleção de canais, pública/privada, com dono; properties `tot_canais`
  e `canais_ativos`.

### 2. Admin (`admin.py`)

- `CanalAdmin` — busca/filtro por status, ação "Desabilita Canal".
- `ListaAdmin` — inline de canais (`Lista.canais.through`) com autocomplete;
  grava o dono no `save_model`.
- `APIKeysAdmin` — escopo por usuário (não superusuário vê só as próprias chaves).
- `TermoStatusAdmin` — registra o modelo `TermoStatus` da `core` filtrado por
  `rede_id = 4`, somente leitura, com coluna derivada de projeto.

### 3. Importação web (`views.py` + `forms.py`)

- `ImportForm` (crispy) — seleção de lista e upload .csv/.xlsx.
- `importacao_canais` — lê CSV (`import_csv`) ou XLSX (`import_xlsx`), normaliza
  usernames (remove `https://t.me/`, `@`, caixa), cria/reaproveita `Canal`,
  associa categorias (respeitando permissão) e adiciona à `Lista`. Montada na
  URLconf da `core` (`telegram/canais/importar/`).

### 4. Sincronização (`management/commands/sync_channels.py`)

Comando assíncrono (`asyncio.run`). `sync_channels(client)` percorre os canais
ativos sem id numérico, resolve a entidade via `get_entity`, enriquece com
`GetFullChannelRequest` e persiste (`asave`). Trata FloodWait (espera), RPCError e
ValueError (desativa o canal). Usa sessão fixa `'sync_channels'` e as chaves
globais de `settings.AUTH_KEYS`.

### 5. Coleta incremental (`management/commands/get_messages.py`)

Núcleo da coleta. Funções:

- `filtro_canal` — resolve um canal por username ou id numérico.
- `monta_peer` — constrói `InputPeerChannel` a partir do `access_hash`
  persistido, evitando `get_entity` (reduz FloodWait).
- `serializa_mensagem` — normaliza uma mensagem telethon no formato do datalake
  (id composto `canal_mensagem`, autor, reply/forward, mídia, métricas).
- `processa_canal` — itera mensagens em ordem cronológica a partir de
  `ultima_mensagem` (ou `DATA_LIMITE`), grava em lotes e avança o ponteiro.
- `coleta_mensagens` — orquestra todos os canais ativos, com backoff aleatório e
  parada após erros consecutivos.

Seleciona credenciais de uma `APIKeys` ativa (sessão `user_<id>`) ou cai para as
chaves globais.

### 6. Exportação (`management/commands/export_telegram.py`)

Classe `Processo` abre conexão PostgreSQL (`connect_postgresql('pg_baoba')`),
cria um registro em `processo`, acumula documentos em `batch` e, no `commit`,
move versões antigas para `historico`, insere na tabela `telegram` e (fora do
modo `--archive`) na `fila_telegram`. Remove os arquivos processados; move
corrompidos para `ruim/`; para após 10 erros.

## Data Models

```
Categoria >──< Canal >──< Lista ──> auth.User (dono)
                 │                     │
                 │                     └── (Projeto.lista_canais na core)
                 ▼
          ultima_mensagem, access_hash, status

APIKeys ──> auth.User            core.TermoStatus ──> core.Termo / core.Rede(4)
```

| Modelo        | Papel |
|---------------|-------|
| `Categoria`   | Rótulo temático de canais (M2M com `Canal`). |
| `Canal`       | Canal/grupo monitorado; metadados + ponteiros de coleta. |
| `APIKeys`     | Credenciais telethon por usuário. |
| `Lista`       | Coleção de canais (pública/privada) ligada a projeto. |
| `core.TermoStatus` | Progresso da coleta por termo na rede Telegram (reutilizado). |

Formato do documento de mensagem (gravado em `data/telegram/*.json`, consumido
por `export_telegram`): `id` (`<id_numerico>_<message_id>`), `channel_id`,
`username`, `message`, `timestamp`, `type` (channel/group), `views`, `forwards`,
`media_type`, `author_id`, `reply_to_msg_id`, `fwd_from_*`, `canal` (FK local).

## Correctness Properties

1. **Coleta resumível e sem recoleta.** `ultima_mensagem` só avança; a próxima
   execução parte dele, de modo que mensagens já capturadas não são relidas.
2. **Idempotência na exportação.** Reexportar um documento com o mesmo `id` move
   a versão anterior para `historico` e substitui — sem duplicar na tabela
   `telegram`.
3. **Identidade estável das mensagens.** O `id` composto
   `<id_numerico>_<message_id>` é único por canal+mensagem, servindo de chave em
   todo o pipeline.
4. **Canais inválidos saem do ciclo.** Username inexistente/erro RPC leva o canal
   a "Não existe mais", evitando retentativas infinitas.
5. **Proteção contra FloodWait.** Preferir `monta_peer` sobre `get_entity` e
   respeitar o tempo de espera do FloodWait mantém a coleta dentro dos limites da
   API.
6. **Terminação sob falha.** A coleta aborta após 10 erros consecutivos,
   evitando varreduras longas em estado degradado.

## Error Handling

- **Sincronização/coleta (telethon).** `FloodWaitError` → espera o tempo indicado
  (sync aguarda e continua; coleta aguarda e segue para o próximo canal).
  `RPCError`/`ValueError` → canal marcado como "Não existe mais" com log.
  `Exception` genérica → log com stacktrace; na coleta, conta para o limite de
  erros consecutivos.
- **Exportação (PostgreSQL).** `commit` em transação; falha faz `rollback` e
  propaga. Arquivo corrompido vai para `ruim/`; vazio é contado como erro; mais de
  10 erros interrompem a varredura.
- **Importação web.** Exceções são capturadas, o traceback é impresso e o usuário
  recebe mensagem genérica de erro via `messages`.
- **Autenticação.** Comandos abortam com mensagem clara quando as chaves não estão
  configuradas ou o usuário telethon não está autorizado.

## Testing Strategy

> Estado atual: sem testes (`telegram/tests.py` vazio). Estratégia recomendada,
> aproveitando o `NoDbTestRunner` do projeto.

- **Unitários puros (`SimpleTestCase`).** `serializa_mensagem` (com objetos
  telethon mockados, cobrindo mídia, reply e forward), `monta_peer` (com/sem
  access_hash), `filtro_canal` e a normalização de username em `import_csv`.
- **Com banco.** Importação (`importacao_canais`): criação/reuso de canais,
  permissão de categoria, adição à lista; e as invariantes de coleta
  (avanço monotônico de `ultima_mensagem`).
- **Exportação.** `Processo.commit` contra um PostgreSQL de teste: movimentação
  para `historico`, inserção em `telegram`/`fila_telegram` e remoção de arquivos.
- **Regressão.** Teste cobrindo a seleção de credenciais em `get_messages`
  (`api_id` deve vir de `chave.api_id`, não de `chave.id` — ver Pontos de atenção).

## Pontos de atenção (design)

> Ver a lista detalhada em `requirements.md`. Em resumo, de natureza
> arquitetural:

1. ~~**Bug de credencial** (`chave.id` vs `chave.api_id`) em `get_messages`.~~
   **(Resolvido)** `api_id` agora vem de `chave.api_id`.
2. **Estratégias de sessão/credencial divergentes** entre `sync_channels` e
   `get_messages`.
3. **Valores hardcoded**: `rede_id = 4`, `DATA_LIMITE`, nomes das tabelas do
   datalake e alias `pg_baoba`. Candidatos a configuração.
4. **Acoplamento ao datalake PostgreSQL externo** via SQL cru específico;
   mudanças de schema no datalake quebram o comando silenciosamente.
5. **Ausência de testes** na lógica de serialização e coleta incremental.
