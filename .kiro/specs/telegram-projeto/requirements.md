# Requisitos — Registro de projeto de coleta Telegram

## Introdução
Nova view `/telegram/projetos/novo/` (app `telegram`) com um formulário para o usuário autenticado registrar um projeto de coleta no Telegram: dados do projeto, lista de canais, período e termos de busca. O painel (`/painel/`) passa a apontar para essa view.

## Requisitos

### 1. Acesso restrito
**User story:** Como usuário, quero que o formulário só esteja disponível autenticado.

Critérios de aceite:
1. WHEN um usuário não autenticado acessa `/telegram/projetos/novo/` THEN o sistema SHALL redirecioná-lo para o login (`/admin/login/`).
2. WHEN um usuário autenticado acessa `/telegram/projetos/novo/` THEN o sistema SHALL exibir o formulário com status 200.

### 2. Campos do formulário
**User story:** Como pesquisador, quero informar os dados da minha pesquisa.

Critérios de aceite:
1. O formulário SHALL ter os campos: **Nome do Projeto** (obrigatório, máx. 40 caracteres, limite de `Projeto.nome`), **Descrição Breve da Pesquisa** (obrigatório, vai para `Projeto.objetivo`), **Lista de canais**, **Data Inicial** e **Data Final** da coleta e **Termos de busca**.
2. O campo **Lista de canais** SHALL oferecer as listas com `publica=True` (exibindo o nome) e as listas privadas cujo `dono` seja o usuário logado.
3. Ao lado da seleção de lista SHALL existir um botão "Importar minha própria lista" que leva à tela de importação de canais (`importacao_canais`).
4. WHEN a Data Final é anterior à Data Inicial THEN o formulário SHALL ser rejeitado com mensagem de erro no campo.
5. O formulário SHALL exibir instrução e exemplos dos conectivos: "Use os conectivos AND e OR em maiúsculas. Exemplos: `ecologia OR ecológico`, `ecologia AND ecológico`."

### 3. Termos de busca
**User story:** Como pesquisador, quero informar vários termos de busca com AND/OR.

Critérios de aceite:
1. O campo de termos SHALL aceitar um termo (expressão) por linha; linhas vazias SHALL ser ignoradas e espaços nas pontas removidos.
2. O sistema SHALL exigir ao menos um termo; cada termo SHALL ter no máximo 2000 caracteres (limite de `Termo.busca`).
3. Os conectivos SHALL ser reconhecidos apenas em maiúsculas (`AND`, `OR`); `and`/`or` em minúsculas são texto comum da busca.
4. WHEN um termo começa ou termina com um conectivo, ou tem conectivos consecutivos (ex.: `ecologia AND OR x`) THEN o formulário SHALL ser rejeitado com mensagem indicando o termo inválido.

### 4. Salvar e iniciar a coleta
**User story:** Como pesquisador, quero salvar o projeto e já deixar a coleta agendada.

Critérios de aceite:
1. WHEN o usuário clica em "Iniciar a coleta" e o formulário é válido THEN o sistema SHALL, em uma única transação, criar o `Projeto` e um `Termo` por linha informada; se qualquer gravação falhar nada SHALL ser persistido.
2. O `Projeto` SHALL ser criado com `usuario` = usuário logado, `lista_canais` = lista escolhida, `redes` contendo a rede Telegram e `status` = Ativo.
3. Cada `Termo` SHALL receber `busca` = texto da linha, `projeto`, `dtinicio` = Data Inicial, `dtfinal` = Data Final e `status` = Ativo; um `TermoStatus` (termo + rede Telegram) SHALL ser criado para cada termo para que a coleta o enxergue.
4. WHEN a gravação conclui THEN o sistema SHALL exibir a mensagem "Para acompanhar o resultado da coleta, clique no link {{projeto.url_resumo}}" (com o link clicável) e redirecionar para `/painel/`.
5. `Projeto.url_resumo` SHALL retornar a URL da página de resumo/estatística do projeto (`core_projeto_stats`).
6. WHEN o formulário é inválido THEN o sistema SHALL reexibir o formulário preservando os valores digitados e indicando os erros, sem gravar nada.

### 5. Integração com o painel
**User story:** Como usuário, quero chegar ao formulário a partir do painel.

Critérios de aceite:
1. O botão "Nova coleta Telegram" de `/painel/` SHALL apontar para `/telegram/projetos/novo/`.
2. A mensagem de sucesso SHALL aparecer no painel (o template do painel SHALL renderizar `messages`).

### 6. Importar lista de canais
**User story:** Como pesquisador, quero subir um arquivo com meus canais para criar uma lista própria e usá-la no projeto.

Critérios de aceite:
1. O botão "Importar lista" do formulário SHALL levar à view `/telegram/listas/importar/`, disponível apenas para usuários autenticados (anônimo → login `/admin/login/`).
2. A view SHALL exibir um formulário com: **Nome da lista** (obrigatório, máx. 100 caracteres), **Visibilidade** (Privada, padrão, ou Pública) e **Arquivo** (.csv ou .xlsx).
3. O formulário SHALL exibir o hint: "O arquivo deve conter apenas uma coluna, com a URL (https://t.me/canal) ou o identificador (@canal) de cada canal."
4. O sistema SHALL ler a primeira coluna do arquivo (CSV: UTF-8, com ou sem BOM; XLSX: primeira planilha), ignorando linhas vazias e uma linha de cabeçalho opcional (`username`, `canal`, `channel`, `url`, `link`, `id`).
5. Cada valor SHALL ser normalizado para o username em minúsculas, aceitando `https://t.me/x`, `t.me/x`, `@x` e `x`; links de mensagem (`t.me/x/123`) SHALL usar apenas `x`. Valores inválidos (convites `t.me/+...`, ids numéricos, caracteres que não comecem com letra, com caracteres fora de `a-z 0-9 _` ou fora de 4 a 32 caracteres) SHALL ser ignorados e contados.
6. Canais que já existem (`Canal.username`) SHALL ser reaproveitados; os novos SHALL ser criados com registro no log. Todos os canais válidos SHALL ser adicionados à lista.
7. A lista SHALL ser criada com `dono` = usuário logado e `publica` conforme a escolha. WHEN o usuário já possui lista com o mesmo nome THEN o formulário SHALL ser rejeitado.
8. O sistema SHALL rejeitar arquivo com mais de 5000 linhas (não há limite de tamanho em bytes) ou sem nenhum canal válido, sem criar a lista; a criação da lista e dos canais SHALL ser atômica.
9. WHEN a importação conclui THEN o sistema SHALL informar totais (lidos, canais novos, ignorados) e redirecionar para `/telegram/projetos/novo/?lista=<id>`, com a nova lista pré-selecionada.

## Fora de escopo
- Iniciar efetivamente a coleta de forma síncrona (a coleta continua sendo feita pelos comandos agendados `sync_channels` e `get_messages`).
- Edição ou exclusão de projetos criados. (A edição foi especificada depois em `telegram-lista-canais`, req. 7.)
- Filtro das mensagens por termo/data durante a coleta e importação integrada da lista (ver Pendências).

## Pendências (em aberto — fora desta entrega)
Esta entrega cobre **apenas o cadastro** (projeto, termos e período). O que falta:

1. **Aplicar termos e período na coleta.** Hoje `get_messages` varre todos os canais ativos sem filtrar por termo ou data (spec `telegram`, req. 4 e 5.3), e `export_telegram` enfileira tudo em `fila_telegram`. Falta: (a) selecionar, na coleta, os canais da `lista_canais` dos projetos ativos; (b) respeitar `Termo.dtinicio`/`dtfinal` ao buscar mensagens; (c) casar as mensagens com a expressão `AND`/`OR` de cada `Termo` e atualizar `TermoStatus`, `last_count` e o status do termo/projeto. Até lá, o link `url_resumo` pode mostrar um resumo vazio.
2. ~~**Importar a própria lista de forma integrada.**~~ **(Resolvido — req. 6.)** Permanece: a tela antiga `importacao_canais` (admin, exige cabeçalho `username` e lista existente) segue como está, com normalização própria duplicada; unificar depois.
3. **Localizar a rede Telegram sem id fixo.** Esta entrega busca `Rede` por nome (`Telegram`, sem diferenciar maiúsculas); o id `4` hardcoded do admin de `TermoStatus` permanece e deve migrar para a mesma estratégia.
4. ~~**Rota.**~~ **(Resolvido — `telegram-lista-canais`, req. 10.)** A rota original `/telegram_project/`, da issue, passou a `/telegram/projetos/novo/`; a antiga redireciona para a nova.
