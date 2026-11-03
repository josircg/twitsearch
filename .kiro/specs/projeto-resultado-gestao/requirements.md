# Requisitos — Resultado do projeto no Gestão (acesso por hash)

## Introdução
Funcionalidade que cruza dois sistemas:

- **Capitu** (este repositório, `twitsearch`): cadastra projetos e termos e controla os usuários. Há **um** ambiente.
- **Gestão Minerva** (repositório irmão `gestao-minerva`): mostra o resultado das buscas (dashboard, dataset, alertas e registros), lendo do OpenSearch. Há **vários** ambientes, cada um com seu `local.py` e seu cadastro de `DataSource`.

Hoje o Gestão abre um dataset inteiro, escolhido por `?ds=<slug>` (ex.: `ds=telegram`). O acesso depende do usuário logado no Gestão pertencer a um grupo do `DataSource`. Alguns usuários do Capitu não terão acesso ao dataset inteiro: devem ver **apenas o próprio projeto**.

O Gestão não acessa o controle de usuários do Capitu. Por isso, o Capitu gera um link para o dashboard no formato `?hash={projeto.id}-{hash}&ds=telegram`, e o Gestão valida o hash. **Quem tem o link vê o resultado daquele projeto, naquele dataset, e só dele, sem login.** Não há chamada entre os sistemas.

### Como o `ds` funciona hoje no Gestão
- `?ds=<slug>` só é lido em `dashboards` e `alerts_view`. Essas views chamam `set_opensearch_index`, que grava `session['opensearch_index']`.
- As outras views (dataset, paginação, filtros, `visualization`, `record_detail`) **não recebem `ds`**. Elas leem o índice da sessão, com padrão `'gestao'`, via `get_opensearch_connection`.
- `set_opensearch_index` e `get_opensearch_connection` exigem que o usuário pertença a um grupo do `DataSource`. Um usuário anônimo é recusado.

O acesso por projeto SHALL seguir o mesmo mecanismo: ser gravado **uma vez** na sessão, junto com o `ds`, e valer em toda a navegação seguinte.

### Premissas
- Nos documentos do OpenSearch, `monitoramento_id` = `Projeto.id`, `monitoramento_nome` = `Projeto.nome` e `busca_id` = `Termo.id` do Capitu.
- **O dataset do link é fixo: `telegram`** (constante `DS_TELEGRAM`), o slug do `DataSource` do Telegram no Gestão. Ele **não** vem de `Projeto.prefix` (req. 3).

## Requisitos — Capitu

### 1. Token de acesso ao resultado
**User story:** Como sistema, quero gerar para cada projeto um token que só o Capitu e o Gestão saibam calcular.

Critérios de aceite:
1. O token SHALL ter o formato `{projeto.id}-{hash}`, com `hash` = HMAC-SHA256 de `"projeto:{projeto.id}:{ds}"`, onde `ds` = `DS_TELEGRAM` (`'telegram'`), usando a chave secreta `PROJETO_HASH_KEY`, em hexadecimal e truncado em 32 caracteres.
2. O `ds` entra no cálculo do hash. Assim, trocar `ds=telegram` por outro dataset invalida o link, e o token não serve para ler um dataset de outra origem, onde `monitoramento_id` pode significar outra coisa.
3. A chave `PROJETO_HASH_KEY` SHALL ser configurada em `local.py`, com o mesmo valor, no Capitu e em todo ambiente do Gestão que aceitar o link (req. 10). Ela SHALL NOT trafegar em URL e é distinta de `AUTH_KEYS`/`CAPITU_KEY`.
4. O token SHALL ser determinístico: o mesmo projeto gera sempre o mesmo token enquanto a chave não mudar.

### 2. Link "Resultado"
Critérios de aceite:
1. `Projeto.url_resultado` SHALL retornar `{GESTAO_URL}/dashboard?hash={token}&ds=telegram`, com os parâmetros codificados (`urlencode`).
2. `url_resultado` SHALL retornar `None` WHEN `GESTAO_URL` ou `PROJETO_HASH_KEY` estiver vazio, ou WHEN o projeto não tiver a rede Telegram.
3. A tabela de projetos de `/painel/` SHALL ganhar a coluna **Resultado**, entre Nome e Status, exibida quando `GESTAO_URL` e `PROJETO_HASH_KEY` estão configurados.
4. Cada linha SHALL exibir um link "Ver resultado" para `url_resultado`, que abre em nova aba (`target="_blank"`, `rel="noopener"`). WHEN `url_resultado` é `None` (projeto sem a rede Telegram) THEN a célula SHALL exibir "—".
5. O link SHALL aparecer em projetos de qualquer status. Projetos ainda sem dados mostram o dashboard vazio (ver Pendências, item 1).
6. (Opcional) O admin de `Projeto` SHALL exibir o mesmo link em `list_display`, para a equipe interna.

### 3. Dataset fixo `telegram`, sem usar o prefixo
**User story:** Como sistema, quero que o link "Resultado" abra sempre o dataset do Telegram, sem depender de um campo que é preenchido à mão.

Critérios de aceite:
1. O `ds` do link e do hash SHALL vir de uma constante única, `DS_TELEGRAM = 'telegram'` (`telegram/models.py`), e não de literais espalhados.
2. O link SHALL NOT usar `Projeto.prefix`. Um prefixo preenchido no admin (ex.: `vtrack-telegram-test`) não altera o link.
3. O formulário `/telegram/projetos/novo/` (`telegram_project`) SHALL NOT gravar `Projeto.prefix`. O campo continua existindo no admin para outros usos, mas fica fora desta funcionalidade.
4. A edição em `editar_projeto` SHALL NOT alterar o prefixo. Ela continua gravando só `nome`, `objetivo` e `lista_canais`.
5. O link SHALL aparecer só para projetos com a rede Telegram. Projetos de outras redes exibem "—" (req. 2.4).

## Requisitos — Gestão

### 4. Entrada pelo link
**User story:** Como pessoa que recebeu o link, quero abrir o resultado do projeto sem ter conta no Gestão.

Critérios de aceite:
1. `GET /dashboard?hash=<token>&ds=<slug>` SHALL ser aceito **sem login**.
2. WHEN o hash é válido para o par (`projeto.id`, `ds`) (recalculado com `PROJETO_HASH_KEY` e comparado com `hmac.compare_digest`) e existe `DataSource` com esse `slug` THEN o sistema SHALL:
   - gravar `session['projeto_acesso'] = projeto.id`;
   - gravar `session['opensearch_index'] = ds`, sem exigir grupo do usuário;
   - redirecionar para `/dashboard`, sem `hash` e `ds` na URL, para que o token não fique no histórico nem no `Referer`.
3. WHEN o hash é malformado, foi alterado, é de outro projeto, ou o `ds` foi trocado ou omitido THEN o sistema SHALL responder 403 e não alterar a sessão.
4. WHEN o hash é válido mas não existe `DataSource` com aquele `slug` no ambiente THEN o sistema SHALL responder 404.
5. WHEN o ambiente não tem `PROJETO_HASH_KEY` configurada THEN o parâmetro `hash` SHALL ser ignorado, e o dashboard segue o fluxo normal (login).
6. A validação SHALL ser só local, sem consultar o Capitu. Um projeto sem documentos resulta em dashboard vazio, não em erro.
7. Abrir um novo link SHALL substituir o projeto e o `ds` anteriores da sessão.

### 5. Persistência na sessão
**User story:** Como pessoa com o link, quero paginar e filtrar sem perder o acesso ao projeto.

Critérios de aceite:
1. Como já acontece com `opensearch_index`, o acesso por projeto SHALL ser lido da sessão em todas as requisições. Paginação, filtros, troca de período, alertas, `visualization` e `record_detail` SHALL manter o acesso sem reenviar `hash`, `ds` ou `monitoramento_id`.
2. No acesso por projeto, um `?ds=` diferente do gravado na entrada SHALL ser ignorado. Para outro dataset é preciso outro link.
3. A checagem de grupo de `set_opensearch_index` e `get_opensearch_connection` SHALL ser dispensada **somente** no acesso por projeto e **somente** para o `ds` gravado na entrada.

### 6. Filtro forçado por projeto
**User story:** Como dono do dado, quero que quem entra pelo link veja apenas os registros do projeto.

Critérios de aceite:
1. No acesso por projeto, toda consulta ao OpenSearch SHALL incluir `monitoramento_id = projeto.id`, aplicado no servidor.
2. O parâmetro `monitoramento_id` da URL ou do POST SHALL ser ignorado nessa sessão.
3. O parâmetro `busca_id` SHALL apenas restringir o resultado dentro do projeto. Um `busca_id` de outro projeto resulta em lista vazia, nunca em dados de outro projeto.
4. Os filtros de período, rede, texto, tipo de conteúdo, publicador e links SHALL continuar funcionando normalmente.
5. O filtro SHALL ser garantido num ponto único, no cliente OpenSearch da sessão, e não em cada construtor de consulta. Hoje `_list_termos_search_query`, `_count_terms_search` e `_filter_options` não aplicam `monitoramento_id`.
6. A página SHALL NOT conter nomes ou ids de outros projetos. A agregação de opções de assunto (`_filter_options`, que alimenta `queryOptions` no dashboard e em `get_alerts`) SHALL ficar restrita ao próprio projeto.
7. Nenhum valor padrão fixo de `monitoramento_id` (como `86` em `opensearch_query.py` e `19` em `dashboards.html`) SHALL ser alcançado nessa sessão.
8. O nome do projeto exibido SHALL vir de `monitoramento_nome` nos próprios documentos já filtrados. Sem documentos, o título é "Projeto {id}".

### 7. Telas disponíveis no acesso por projeto
**User story:** Como pessoa com o link, quero ver os dashboards, as listas e as demais telas de resultado do projeto, sem acesso ao admin.

Critérios de aceite:
1. As seguintes telas SHALL ficar disponíveis, sempre com o filtro do req. 6:
   - dashboard;
   - dataset (lista, paginação e filtros);
   - `visualization/<id>` e `record_detail/<id>`;
   - alertas;
   - `monitoramentos/<id>/buscas`, só para o próprio id;
   - interpretação por IA dos gráficos (`dashboard/interpret-graph`).
2. Em `visualization` e `record_detail`, WHEN o registro pedido não pertence ao projeto (`monitoramento_id` diferente) THEN o sistema SHALL responder 404.
3. O admin (`/admin/`) continua exigindo login de staff e SHALL NOT ser liberado pelo link.
4. SHALL ficar indisponíveis, com 403 ou redirecionamento para o dashboard do projeto:
   - menu e pastas do GED;
   - cadastro de tags;
   - migrations, deploy e debug;
   - `log_query`;
   - feedback de IA (`ia/feedback`, que grava `user_created` e exige usuário).
5. As ações que alteram registros no dataset (POST de arquivar e de aplicar tag) SHALL ser recusadas com 403, e os checkboxes e o seletor de ação SHALL ficar ocultos. Essas ações alteram o dado compartilhado com a equipe interna.
6. O dashboard SHALL exibir o nome do projeto como título e SHALL ocultar o seletor de assunto/monitoramento, o botão "Limpar" do monitoramento e o formulário de feedback da IA.
7. A barra de navegação SHALL ocultar "Menu", "Alterar senha" e "Logout" quando o acesso é só por projeto, sem usuário logado.

### 8. Exportação CSV bloqueada
**User story:** Como dono do dado, quero que o link permita só visualizar, sem baixar o dataset.

Critérios de aceite:
1. No acesso por projeto, o botão "Baixar csv" SHALL ficar oculto na tela do dataset.
2. WHEN chega um POST `action=export` no acesso por projeto THEN o sistema SHALL responder 403 e SHALL NOT disparar o pipeline de exportação (Mage).
3. Para usuários logados, sem acesso por projeto, a exportação SHALL continuar como hoje (arquivo enviado para `request.user.email`).

### 9. Convivência com o login normal
**User story:** Como usuário interno do Gestão, quero continuar usando os datasets normalmente.

Critérios de aceite:
1. Sem `hash` na URL e sem acesso por projeto na sessão, o comportamento atual (login + `?ds=` + grupos do `DataSource` + índice na sessão) SHALL ficar inalterado.
2. WHEN um usuário **logado** com permissão num `DataSource` usa `?ds=<slug>` sem `hash` THEN o acesso por projeto da sessão SHALL ser removido e o dataset escolhido aberto normalmente. Isso sai do "modo projeto".
3. Para um usuário anônimo, `?ds=` sem `hash` nunca remove o acesso por projeto (req. 5.2).

### 10. Vários ambientes do Gestão, um Capitu
Critérios de aceite:
1. O Capitu SHALL ter **um** `GESTAO_URL`: o ambiente para onde vai o link "Resultado".
2. Todo ambiente do Gestão que aceitar o link SHALL ter a mesma `PROJETO_HASH_KEY` do Capitu. O token não depende do ambiente: o mesmo link funciona em qualquer ambiente com a chave e com um `DataSource` daquele `slug`, trocando apenas o domínio.
3. Um ambiente sem a chave ignora o `hash` (req. 4.5). Um ambiente sem o `DataSource` responde 404 (req. 4.4).
4. Trocar a chave SHALL ser feito no Capitu e em todos os ambientes do Gestão ao mesmo tempo. Isso invalida todos os links já distribuídos.

### 11. Segurança do token
Critérios de aceite:
1. A validação SHALL usar comparação em tempo constante (`hmac.compare_digest`).
2. O token SHALL NOT ser registrado em logs de aplicação. Os logs registram apenas o `projeto.id` e o `ds`.
3. O acesso por projeto na sessão SHALL expirar junto com a sessão do Django (`SESSION_COOKIE_AGE`). Para voltar, basta abrir o link de novo.

## Fora de escopo
- Qualquer API ou chamada entre Capitu e Gestão para esta funcionalidade.
- Usar `Projeto.prefix` para escolher o dataset do link, ou gravar prefixo pelo formulário Telegram.
- Link "Resultado" para projetos de outras redes (Twitter/YouTube).
- Filtrar o painel por rede. Ele continua listando todos os projetos do usuário (spec `painel-projetos`, req. 4.1), e a coluna "Resultado" mostra o link só para os projetos Telegram.
- Revogar o link de um projeto específico (ver Decisões, item 4).
- Criar usuários no Gestão a partir do Capitu, ou sincronizar usuários entre os dois.
- Alterar o pipeline de ingestão (Mage/vtrack) ou o mapeamento dos documentos no OpenSearch.

## Pendências
1. **Pré-requisito para projetos Telegram.** A pendência P1 de `telegram-projeto` continua aberta: a coleta não associa as mensagens a termos e projetos, e `export_telegram` não filtra por termo. Enquanto isso não for resolvido, provavelmente não haverá documentos com o `monitoramento_id` desses projetos, e o link "Resultado" abrirá um dashboard vazio.
2. **Valores fixos no Gestão.** `monitoramento_id: 86` (`opensearch_query.py`) e `'19'` (`dashboards.html`) devem ser revistos no fluxo normal. Esta entrega apenas garante que o acesso por projeto não chegue a eles.
3. **`DataSource` `telegram` em cada ambiente.** O Gestão responde 404 ao link se o ambiente não tiver um `DataSource` com slug `telegram`. Ele deve existir e apontar para o índice onde ficam os documentos do Telegram.

## Decisões
1. **Ambiente de destino:** único. O link "Resultado" sempre aponta para o `GESTAO_URL` configurado no Capitu (req. 10.1).
2. **Ações de escrita no dataset:** bloqueadas pelo link. Arquivar e aplicar tag continuam restritos a usuários logados (req. 7.5).
3. **Dataset do link:** fixo em `telegram` (`DS_TELEGRAM`), sem usar `Projeto.prefix`. Antes o link usava o prefixo; um prefixo preenchido à mão em produção (`vtrack-telegram-test`) apontava para um dataset inexistente no Gestão e dava 404 (req. 3).
4. **Revogação:** fica fora de escopo. Hoje só é possível trocando a chave em todos os ambientes (req. 10.4), o que derruba todos os links.
5. **Exportação CSV:** bloqueada pelo link (req. 8). O link serve só para visualizar.
