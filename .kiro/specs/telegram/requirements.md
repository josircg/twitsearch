# Requirements Document

_App `telegram` do Capitu._

> **Natureza deste documento.** Documentação de **engenharia reversa** do
> comportamento atual da app `telegram`. Descreve o que o sistema faz hoje, para
> servir de referência de manutenção. Pontos de atenção e sugestões de melhoria
> estão reunidos ao final.

## Introduction

A app `telegram` adiciona ao Capitu a coleta de dados de canais do Telegram,
espelhando o modelo do Twitter da app `core`: cadastro de canais (por lista e
categoria), sincronização de metadados, captura incremental de mensagens e
exportação para um datalake em PostgreSQL. A coleta usa a biblioteca `telethon`
sobre a API do Telegram e roda via *management commands* assíncronos.

A app reutiliza infraestrutura da `core` (logging, conexão PostgreSQL,
`alog_message`, layouts crispy) e integra-se ao fluxo de projetos pela rede
"Telegram" e pelo modelo `TermoStatus` (que registra o progresso da coleta por
termo/rede).

Atores:

- **Pesquisador/operador**: cadastra canais (manualmente ou por importação de
  CSV/XLSX), organiza-os em listas e categorias, e cadastra suas chaves de API.
- **Agendador** (cron): dispara `sync_channels`, `get_messages` e
  `export_telegram`.
- **Datalake externo (Mage/PostgreSQL)**: consome as mensagens exportadas.

## Glossary

- **Canal**: canal ou grupo do Telegram monitorado (username, id numérico,
  metadados, status).
- **Categoria**: rótulo temático aplicável a canais.
- **Lista**: coleção de canais (pública ou privada), associável a um projeto da
  `core` via `Projeto.lista_canais`.
- **APIKeys**: credenciais de API do Telegram (api_id/api_hash) por usuário,
  usadas pelo `telethon`.
- **Datalake**: base PostgreSQL de destino (tabelas `telegram`, `historico`,
  `fila_telegram`) consumida pela pipeline externa.
- **Sincronização**: obtenção dos metadados de um canal (id numérico, título,
  access_hash, participantes) a partir do username.
- **Coleta incremental**: captura de mensagens novas a partir do ponteiro
  `ultima_mensagem` de cada canal.

## Requirements

### Requisito 1 — Cadastro e organização de canais

**User story:** Como pesquisador, quero cadastrar e organizar canais do Telegram
em listas e categorias, para definir o que será coletado.

#### Critérios de aceitação

1. O sistema DEVE permitir cadastrar canais com username único e armazenar seus
   metadados (título, sobre, participantes, mensagens, status, access_hash).
2. O sistema DEVE permitir agrupar canais em `Categoria` e em `Lista` (pública ou
   privada), e associar uma `Lista` a um projeto da `core`.
3. QUANDO uma `Lista` é salva no admin, O sistema DEVE registrar o usuário
   autenticado como dono.
4. QUANDO o operador executa a ação "Desabilita Canal", O sistema DEVE marcar os
   canais selecionados como Inativo.
5. O sistema DEVE expor contadores de total de canais e canais ativos por lista e
   total de canais por categoria.

### Requisito 2 — Importação de canais por arquivo

**User story:** Como pesquisador, quero importar canais a partir de um arquivo
CSV ou XLSX, para cadastrar muitos canais de uma vez.

#### Critérios de aceitação

1. QUANDO o usuário envia um arquivo .csv ou .xlsx na tela de importação, O
   sistema DEVE ler os registros com ao menos a coluna `username`.
2. QUANDO um username vem como URL (`https://t.me/...`) ou com `@`, O sistema DEVE
   normalizá-lo para o identificador simples em minúsculas.
3. QUANDO um canal ainda não existe, O sistema DEVE criá-lo e registrar a origem
   no log (LogEntry); canais existentes DEVEM ser reaproveitados.
4. SE o registro trouxer categoria E o usuário for superusuário, ENTÃO O sistema
   DEVE criar a categoria se não existir; caso contrário, DEVE usar apenas
   categorias já existentes.
5. QUANDO a importação conclui, O sistema DEVE adicionar os canais à lista
   escolhida e informar os totais de registros lidos e incluídos.
6. SE nenhum registro válido for encontrado, ENTÃO O sistema DEVE informar erro
   sem alterar dados.

### Requisito 3 — Sincronização de metadados dos canais

**User story:** Como operador, quero sincronizar os metadados dos canais, para
obter id numérico, título e access_hash necessários à coleta.

#### Critérios de aceitação

1. QUANDO `sync_channels` é executado, O sistema DEVE processar os canais ativos
   que ainda não têm id numérico.
2. QUANDO o canal é resolvido como Channel, O sistema DEVE preencher id numérico,
   título, access_hash, participantes, megagroup, data de criação e descrição
   (via `GetFullChannelRequest`) e registrar sucesso no log.
3. QUANDO o username não resolve (ValueError) ou a API retorna erro RPC, O sistema
   DEVE marcar o canal como "Não existe mais" e registrar o motivo.
4. QUANDO a API do Telegram retorna FloodWait, O sistema DEVE aguardar o tempo
   indicado antes de continuar.
5. SE as chaves de API do Telegram não estiverem configuradas OU o usuário não
   estiver autorizado, ENTÃO O sistema DEVE abortar informando o problema.

### Requisito 4 — Coleta incremental de mensagens

**User story:** Como operador, quero capturar as mensagens novas dos canais de
forma incremental e resumível, para manter a base atualizada sem recoletar tudo.

#### Critérios de aceitação

1. QUANDO `get_messages` é executado, O sistema DEVE processar os canais ativos
   com id numérico, em ordem de data da última carga.
2. QUANDO o canal já foi coletado, O sistema DEVE buscar apenas mensagens a partir
   do ponteiro `ultima_mensagem`; caso contrário, DEVE partir de uma data limite
   configurada.
3. O sistema DEVE montar o peer a partir do `access_hash` já persistido, evitando
   um round-trip `get_entity` (fonte comum de FloodWait); SE não houver
   access_hash, ENTÃO DEVE resolver via `get_entity` e regravar os dados.
4. QUANDO captura mensagens, O sistema DEVE gravá-las em arquivos JSON em lotes
   (`data/telegram/`) e avançar o ponteiro `ultima_mensagem` a cada lote.
5. QUANDO conclui um canal, O sistema DEVE atualizar `dt_ultima_carga` e o total
   de mensagens, e registrar no log.
6. QUANDO a API retorna FloodWait, O sistema DEVE aguardar e seguir para o próximo
   canal; QUANDO retorna erro RPC, DEVE desativar o canal.
7. SE ocorrerem erros consecutivos acima do limite (10), ENTÃO O sistema DEVE
   abortar a execução.
8. QUANDO chamado com `--fake`, O sistema NÃO DEVE gravar arquivos nem atualizar
   os canais.
9. O sistema DEVE usar as credenciais de uma `APIKeys` ativa quando houver;
   caso contrário, DEVE usar as chaves globais de `settings.AUTH_KEYS`.

### Requisito 5 — Exportação para o datalake PostgreSQL

**User story:** Como operador, quero exportar as mensagens coletadas para o
datalake, para que sejam processadas pela pipeline externa.

#### Critérios de aceitação

1. QUANDO `export_telegram` é executado, O sistema DEVE varrer os JSON de
   `data/telegram/` e inserir os documentos na tabela `telegram` do PostgreSQL em
   lotes.
2. QUANDO um documento já existe, O sistema DEVE mover a versão anterior para a
   tabela `historico` antes de inserir a nova.
3. EXCETO no modo `--archive`, O sistema DEVE inserir o lote inteiro na tabela
   `fila_telegram` (toda mensagem vem de canal ativo, sem filtro por termo).
4. QUANDO um arquivo é processado com sucesso, O sistema DEVE removê-lo; arquivos
   corrompidos DEVEM ir para `data/telegram/ruim/`.
5. SE ocorrerem mais de 10 erros, ENTÃO O sistema DEVE interromper a varredura.
6. QUANDO chamado com `--estimate`, O sistema DEVE apenas contar os arquivos sem
   processá-los.

### Requisito 6 — Visibilidade do status da coleta (admin)

**User story:** Como operador, quero ver o status da coleta por termo no admin,
para acompanhar o progresso da rede Telegram.

#### Critérios de aceitação

1. O sistema DEVE exibir `TermoStatus` filtrado pela rede Telegram (id 4) no
   admin, com projeto, termo, status e ponteiro de processamento.
2. ENQUANTO o usuário não for superusuário, O admin de `APIKeys` DEVE exibir
   apenas as chaves do próprio usuário.
3. QUANDO uma `APIKeys` é salva, O sistema DEVE registrar o usuário autenticado
   como dono.

## Pontos de atenção (dívidas técnicas e riscos)

1. ~~**Bug crítico — api_id incorreto em `get_messages`.** No `Command.handle`,
   `options['api_id'] = chave.id` usa o **PK do registro `APIKeys`**, não o campo
   `chave.api_id`.~~ **(Resolvido)** A atribuição passou a usar `chave.api_id`. A
   sessão `user_<chave.id>` foi mantida (o PK é legítimo como nome único de
   sessão).
2. **Sessão divergente entre comandos.** `sync_channels` usa a sessão fixa
   `'sync_channels'` e as chaves globais; `get_messages` usa `user_<id>` com as
   chaves da `APIKeys`. Isso pode exigir logins separados por sessão. *Sugestão:*
   padronizar a estratégia de sessão/credencial.
3. **`rede_id = 4` hardcoded** no admin de `TermoStatus` (mesma fragilidade da
   `core`). *Sugestão:* referenciar a rede Telegram por slug/configuração.
4. ~~**`importacao_canais` usa `erros` possivelmente indefinida.** No ramo POST
   com formulário inválido, `erros` não é atribuída antes do `render`.~~
   **(Resolvido)** `erros` passou a ser inicializada (`erros = None`) no início
   da view, eliminando o risco de `UnboundLocalError`.
5. **Datas/limites hardcoded.** `DATA_LIMITE = 2025-01-01` fixo no código define o
   início da coleta para canais novos. *Sugestão:* tornar configurável por canal
   ou por settings.
6. **Nome/estrutura do datalake acoplados** (tabelas `telegram`/`historico`/
   `fila_telegram`, alias `pg_baoba`) fixos no comando. *Sugestão:* mover para
   configuração.
7. **Ausência de testes** (`telegram/tests.py` vazio), incluindo a serialização de
   mensagens e a lógica incremental. *Sugestão:* cobrir `serializa_mensagem` e
   `monta_peer` com `SimpleTestCase`.
