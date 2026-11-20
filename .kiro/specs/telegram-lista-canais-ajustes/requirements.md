# Requisitos — Ajustes da issue #40 (menu, link do canal e índice do projeto no "Resultado")

## Introdução
Correções pedidas pelo admin no comentário de 20/11/2026 da issue [#40](https://github.com/josircg/twitsearch/issues/40), depois do PR #41 (spec original: `.kiro/specs/telegram-lista-canais/`). O comentário de 20/11/2026 da issue [#36](https://github.com/josircg/twitsearch/issues/36) completa o item 3.

1. Os links do menu superior não funcionam.
2. Na lista de canais, os usuários clicam no link que leva ao Telegram em vez de clicar no que leva às mensagens. O ícone desse link deve ser trocado pelo do Telegram, e o clique no título do canal deve abrir as mensagens.
3. O projeto 100 deixou de aparecer no painel do Gestão quando o admin trocou o índice do projeto de `telegram` para `capitu`.

### Diagnóstico
1. **Menu.** Os itens do menu de `base.html` são âncoras locais (`#main`, `#como-funciona`, `#acesso`, `#institucional`). Os alvos existem só em `home.html`, então nas outras telas (painel, listas, canal, projeto) o clique não faz nada. O logo aponta para `#`, e a rota `^$` (`index`) não tem `name=`.
2. **Link do canal.** No grid de `/telegram/listas/`, o `@usuario` é o link para `https://t.me/<usuario>` (com um ícone genérico de "link externo"). O link para as mensagens fica só no número da coluna "Mensagens coletadas". O título do canal (`titulo`) é texto puro.
3. **Projeto 100.**
   - `Projeto.prefix` ("Elastic Prefix" no admin) é o que a API envia como `projeto_index`.
   - O `vtrack-consumidor` grava as mensagens no índice `{prefix}-{ano}-{mês}-1` (`custom/telegram_vtracker.py`). Com o prefixo `capitu`, os documentos novos vão para `capitu-2026-11-1`.
   - O link "Ver resultado" abre sempre `…/dashboard?hash=…&ds=telegram`, por decisão do req. 3 de `projeto-resultado-gestao`.
   - No Gestão, `ds` é o **slug do `DataSource`**, não o índice. O índice lido vem de `DataSource.conexao['index']` (ex.: `telegram*`), que não alcança `capitu-*`. Por isso o dashboard do projeto fica vazio.
   - Resposta à pergunta do admin na #36 ("O 'telegram' é o índice ou é o dataset do gestão?"): é o dataset (o slug do `DataSource`) do Gestão.

> Interpretação (item 3): "listagem do painel" é o painel (dashboard) do Gestão aberto por "Ver resultado", e não o `/painel/` do Capitu. O `/painel/` filtra só por `usuario`, e a troca do prefixo no admin não altera o `usuario` (`save_model` só o grava na criação). A tarefa 1 confirma isso em produção.

### Restrição
No Gestão, tudo passa pelo `DataSource` (conexão, credenciais e permissão por grupo). A mudança SHALL se limitar ao caminho de acesso por projeto (o link com `hash`, criado na #36), sem alterar o fluxo de quem entra logado e escolhe o dataset.

## Requisitos

### 1. Menu superior funcionando em todas as telas
**User story:** Como usuário em qualquer tela, quero que o menu do cabeçalho me leve às seções da página inicial.

Critérios de aceite:
1. A rota `^$` SHALL ter `name='index'`.
2. O logo e o item **Início** SHALL apontar para a página inicial (`{% url 'index' %}`).
3. **Como funciona**, **Como ter acesso** e **Institucional** SHALL apontar para `{% url 'index' %}#como-funciona`, `#acesso` e `#institucional`, respectivamente.
4. WHEN o usuário está fora da página inicial (ex.: `/painel/`, `/telegram/listas/`, `/telegram/canais/<id>/`) THEN o clique SHALL abrir a página inicial já posicionada na seção.
5. WHEN o usuário já está na página inicial THEN o clique SHALL rolar até a seção, sem perder o comportamento atual.
6. O título da seção de destino NÃO SHALL ficar escondido atrás do cabeçalho fixo (`sticky-top`), em 1280px e em 390px.
7. No celular (menu recolhido do `navbar-expand-lg`), os mesmos links SHALL funcionar.
8. "Acessar Sistema" continua como hoje (`{% url 'login' %}`).

### 2. Canal: título leva às mensagens, ícone do Telegram leva ao Telegram
**User story:** Como pesquisador, quero clicar no nome do canal e cair nas mensagens coletadas, e ainda ter um atalho claro para abrir o canal no Telegram.

Este requisito substitui o critério 4.2 de `telegram-lista-canais` no que diz respeito aos links da coluna Canal.

Critérios de aceite:
1. No grid de `/telegram/listas/`, o `@usuario` e o título do canal (`titulo`) SHALL formar um único link para `/telegram/canais/<Canal.pk>/`, com o mesmo `?voltar=` do link de mensagens. O link abre na mesma aba.
2. Ao lado do `@usuario` SHALL haver um link só com ícone, com o **logo do Telegram** (avião de papel), para `https://t.me/<usuario>`. Ele abre em nova aba (`target="_blank"`, `rel="noopener"`), com `aria-label="Abrir @<usuario> no Telegram (nova aba)"` e `title="Abrir no Telegram"`.
3. O ícone genérico de "link externo" SHALL deixar de ser usado nesses links.
4. O número em "Mensagens coletadas" continua sendo link para as mensagens (req. 4.3 de `telegram-lista-canais`).
5. No celular (cartões), o link do ícone SHALL ter alvo de toque de pelo menos 44px × 44px e NÃO SHALL causar rolagem horizontal em 390px.
6. O ícone SHALL usar a cor de link do sistema (`#0066FF`; `#0052CC` no hover) e foco visível por teclado.
7. Na página do canal (`/telegram/canais/<id>/`):
   1. o link `@usuario` do cabeçalho continua levando ao Telegram (a tela já é a das mensagens), mas o ícone genérico SHALL ser trocado pelo logo do Telegram;
   2. o link "Abrir no Telegram" de cada mensagem (`tc-m-link`) SHALL usar o mesmo logo.
8. Canais com status diferente de Ativo continuam com o selo de status (req. 4.8 de `telegram-lista-canais`).

> Interpretação: o pedido fala do grid ("ao clicar no título do canal"). A troca do ícone no cabeçalho e nas mensagens da página do canal é para manter um único símbolo para "abrir no Telegram" em todo o produto.

### 3. Link "Resultado" com o índice do projeto
**User story:** Como admin, quero trocar o índice em que um projeto grava (`prefix`) e continuar vendo o resultado dele no Gestão pelo link "Ver resultado".

Este requisito revoga os critérios 3.2 de `projeto-resultado-gestao` ("O link SHALL NOT usar `Projeto.prefix`") e 1.1 da mesma spec (fórmula do hash), nos termos abaixo. O `ds` continua fixo em `telegram` (`DS_TELEGRAM`): ele escolhe a conexão (o `DataSource`), e o índice passa a vir do projeto.

#### Capitu
Critérios de aceite:
1. WHEN `Projeto.prefix` está preenchido e segue a regra de índice (`^[a-z][a-z0-9-]{0,19}$`: minúsculas, dígitos e `-`, começando por letra, até 20 caracteres) THEN `url_resultado` SHALL retornar `{GESTAO_URL}/dashboard?hash={token}&ds=telegram&idx={prefix}`, com os parâmetros codificados (`urlencode`).
2. WHEN `Projeto.prefix` está vazio ou não segue a regra de índice (ex.: prefixos antigos, anteriores ao `clean_prefix`, com maiúsculas, `*` ou começando por `-`) THEN `url_resultado` SHALL retornar exatamente o link de hoje (sem `idx`), com o mesmo token. Links já distribuídos continuam válidos.
3. O hash SHALL cobrir o índice: HMAC-SHA256 de `"projeto:{id}:{ds}:{idx}"` quando há `idx`, e de `"projeto:{id}:{ds}"` quando não há (fórmula de hoje), com a mesma chave `PROJETO_HASH_KEY`, em hexadecimal, truncado em 32 caracteres. Trocar ou remover o `idx` da URL SHALL invalidar o link.
4. As demais regras de `url_resultado` não mudam: `None` sem `GESTAO_URL` ou `PROJETO_HASH_KEY`, ou sem a rede Telegram; coluna "Resultado" no painel e no `list_display` do admin.
5. WHEN o admin altera o prefixo THEN o link SHALL mudar junto. O link antigo (com o prefixo anterior ou sem `idx`) continua válido para o índice que ele carrega.
6. WHEN um projeto é criado por `/telegram/projetos/novo/` (`telegram_project`) THEN o sistema SHALL gravar `prefix = 'telegram'` (constante `PREFIXO_TELEGRAM`, `telegram/models.py`), sem campo na tela. O projeto nasce gravando em `telegram-*`, e o link leva `idx=telegram`. Revoga o req. 3.3 de `projeto-resultado-gestao`.
6.1. `editar_projeto` continua sem gravar `prefix` (req. 3.4 de `projeto-resultado-gestao`): um prefixo trocado no admin é mantido, e um prefixo vazio continua vazio.

#### Gestão (`gestao-minerva`)
Critérios de aceite:
7. `GET /dashboard?hash=<token>&ds=<slug>&idx=<índice>` SHALL ser aceito sem login, como hoje. O `idx` é opcional.
8. O `idx` SHALL ser validado com a mesma regra de índice do critério 1 (`^[a-z][a-z0-9-]{0,19}$`). Um valor fora da regra SHALL resultar em 403, sem alterar a sessão.
9. WHEN o hash é válido para (`projeto.id`, `ds`, `idx`) e existe `DataSource` com o slug `ds` THEN o sistema SHALL gravar na sessão, além do que já grava (`projeto_acesso`, `projeto_ds`, `opensearch_index`), `projeto_indice = idx`, e redirecionar para `/dashboard` sem os parâmetros.
10. Hash alterado, de outro projeto, com `ds` ou `idx` trocados, removidos ou acrescentados SHALL resultar em 403, sem alterar a sessão (como o req. 4.3 de `projeto-resultado-gestao`).
11. No acesso por projeto com `projeto_indice`, todas as consultas SHALL usar o padrão de índice `{idx}-*` no lugar de `DataSource.conexao['index']`. A conexão (host, porta, credenciais) continua sendo a do `DataSource` `ds`.
12. No acesso por projeto sem `projeto_indice` (link sem `idx`), o comportamento SHALL ser o de hoje.
13. O filtro forçado por `monitoramento_id` (`ClienteProjeto`) e o bloqueio de escrita continuam valendo com o índice do projeto.
14. Abrir um novo link SHALL substituir o projeto, o `ds` e o índice anteriores da sessão. Entrar logado e escolher um dataset (`set_opensearch_index`) SHALL limpar também o `projeto_indice`.
15. O fluxo de quem entra logado e escolhe o dataset pelo `?ds=` NÃO SHALL mudar: mesma checagem de grupo, mesmo índice do `DataSource`.

## Fora de escopo
- Criar um `DataSource` por prefixo no Gestão. A solução usa o `DataSource` `telegram` para a conexão (ver "Alternativas" no design).
- Mover para `capitu-*` os documentos do projeto 100 que ficaram no índice antigo (`telegram*`). Com o `idx`, o resultado mostra só o que está no índice atual do projeto (ver Pendência 1).
- Links de resultado para redes que não são o Telegram.
- Mudar "Acessar Sistema" para usuários já autenticados.
- Erro `GET /static/config.js` no `gestao-capitu` (comentário da #36; ver Pendência 3).

## Pendências (em aberto — fora desta entrega)
1. **Dados do índice antigo.** Os documentos do projeto 100 gravados antes da troca continuam em `telegram*`. Para aparecerem no resultado, mover com `dashboards/management/commands/move.py` do Gestão (por `monitoramento_id`) ou decidir que o link consulte também o índice do `DataSource` (`{idx}-*,<índice do DataSource>`). Decisão do admin.
2. **Mesmo cluster.** A solução supõe que o índice do projeto está no mesmo OpenSearch do `DataSource` `telegram`. Se algum prefixo for gravado em outro cluster, será preciso um `DataSource` próprio.
3. **`/static/config.js` no `gestao-capitu`.** O arquivo é pedido pelo CKEditor (`ckeditor.js` carrega `config.js` a partir do seu caminho base). O pedido em `/static/` sugere `CKEDITOR_BASEPATH` ausente ou estáticos do CKEditor fora do lugar nessa instância. Tratar na #36 ou numa issue própria.
4. **Prefixo vazio.** Sem prefixo, o consumidor grava em `vtrack-prod-*`, e o link sem `idx` abre o índice do `DataSource` `telegram`. Esse caso não muda nesta entrega.
5. **Outros projetos com prefixo.** O req. 3 vale para todo projeto Telegram com prefixo válido, não só para o 100: o link deixa de abrir o índice do `DataSource` e passa a abrir `{prefix}-*`. A tarefa 1 lista esses projetos em produção e confirma onde estão os documentos de cada um antes do deploy.
