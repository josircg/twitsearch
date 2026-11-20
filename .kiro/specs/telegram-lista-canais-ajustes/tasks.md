# Tarefas — Ajustes da issue #40 (menu, link do canal e índice do projeto no "Resultado")

## Antes da implementação
- [x] 0. Aprovar com o usuário esta spec, em especial a solução do item 3 (`idx` no link, `ds` fixo em `telegram`) e a Pendência 1 (dados do índice antigo)
  - Feito (20/11): opção A aprovada pelo usuário. A Pendência 1 (dados antigos do projeto 100) continua em aberto.
- [ ] 1. Confirmar em produção (diagnóstico do req. 3; nada é alterado):
  - projeto 100: `prefix`, `redes`, `usuario` e se ele aparece no `/painel/` do dono (descarta a leitura "painel do Capitu");
  - índices com `monitoramento_id = 100` (`telegram*` e `capitu-*`) e quantidade de documentos em cada um;
  - `DataSource` do Gestão no ambiente de `GESTAO_URL`: se o slug é mesmo `telegram` (o script de cadastro usa `vtrack-telegram`), o `conexao['index']` e se está no mesmo cluster que `capitu-*` (Pendência 2);
  - todos os projetos Telegram com `prefix` preenchido: se o prefixo segue `^[a-z][a-z0-9-]{0,19}$` e se os documentos estão em `{prefix}-*` (Pendência 5);
  - que o pipeline do Mage em produção não define `fixed_index` no `telegram_vtracker` (se definir, o prefixo não controla o nome do índice e o diagnóstico muda)

## 1. Menu superior (req. 1)
- [x] 2. `name='index'` na rota `^$` em `core/urls.py`
- [x] 3. `templates/base.html`: logo e "Início" com `{% url 'index' %}`; "Como funciona", "Como ter acesso" e "Institucional" com `{% url 'index' %}#…`
- [x] 4. Conferir no navegador (1280px e 390px, menu recolhido) a partir de `/painel/`, `/telegram/listas/` e da própria home; se o título da seção ficar sob o cabeçalho fixo, aplicar `scroll-margin-top` escopado aos três alvos (req. 1.6)
  - Feito (20/11): Chrome headless, 1280px e 390px; cabeçalho com 74px, títulos das três seções aparecem inteiros abaixo dele, então `scroll-margin-top` não foi necessário. Não medido: menu do celular aberto (continua aberto ao clicar num link da própria home, como antes).
- [x] 5. Testes: links do `nav` em `/painel/` e `/telegram/listas/`

## 2. Link do canal (req. 2)
- [x] 6. `templates/_icone_telegram.html` com o SVG do logo do Telegram (`currentColor`, tamanho por variável)
- [x] 7. `templates/lista_canais.html`: `@usuario` + título em um link para `canal_mensagens` (com `voltar_qs`); link só com ícone para `t.me` ao lado (req. 2.1–2.4)
- [x] 8. `templates/canal_mensagens.html`: logo do Telegram no `tc-canal-link` do cabeçalho e no `tc-m-link` de cada mensagem (req. 2.7)
- [x] 9. CSS `#telegram-canais`: `.tc-canal-linha`, `.tc-canal-msgs` (hover no `@usuario`), `.tc-tg` (32px no desktop, 44px no celular, foco visível) (req. 2.5, 2.6)
- [x] 10. Testes: links da coluna Canal e ícone na página do canal; ajustar as asserções antigas que esperam `t.me` no `@usuario` do grid
- [x] 11. Conferir no navegador (1280px e 390px): clique no título abre as mensagens com a seleção preservada no "Voltar às listas"; ícone abre o Telegram em nova aba; sem rolagem horizontal em 390px
  - Feito (20/11): sem rolagem horizontal em 1280px e 390px; `.tc-tg` com 32x32 e 44x44. Não testado no navegador: o clique em si (coberto pelos testes de `href` e `voltar`).
- [x] 12. Atualizar o protótipo do Claude Design (`Main`, `ListaMobile`, `Canal`, `CanalMobile`) com o ícone e o link no título
  - Feito (20/11): versão 31 do protótipo. Lista (desktop e celular) com `@usuario` + título levando à tela Canal e botão redondo com o logo (32px/44px); tela do canal com o logo no `@usuario` do cabeçalho e no link de cada mensagem (no celular continua "Telegram ↗"). Conferido no Chrome headless; o hover não foi conferido com o mouse.

## 3. Índice do projeto no "Resultado" (req. 3)

### Gestão (`gestao-minerva`) — publicar primeiro
- [x] 13. Conferir que todas as views que montam `msearch` usam o `index_name` de `get_opensearch_connection` nos cabeçalhos
  - Feito (20/11): só `filter_dashboard` e a consulta de alertas usam `msearch`; ambas recebem `index=index_name` de `get_opensearch_connection`, com cabeçalhos `{}`. Nada a corrigir.
- [x] 14. `utils/hash_projeto.py`: `hash_projeto` e `valida_hash` com `indice=''` (req. 3.3)
- [x] 15. `dashboards/opensearch/session.py`: `projeto_indice` em `set_projeto_acesso`, `limpa_projeto_acesso` e `get_projeto_indice` (req. 3.9, 3.14)
- [x] 16. `dashboards/decorators.py`: ler e validar `idx`, repassar a `valida_hash` e a `set_projeto_acesso` (req. 3.7, 3.8, 3.10)
- [x] 17. `dashboards/opensearch/datasource.py`: `{idx}-*` no acesso por projeto com `projeto_indice` (req. 3.11–3.13)
- [x] 18. Testes em `dashboards/tests.py` conforme o design, com o hash fixado de (`100`, `telegram`, `capitu`)
  - Feito (20/11): worktree `gestao-minerva-issue40`, branch `feature/indice-projeto`; 70 testes passando (eram 56). O vetor do hash usa a constante `CHAVE` existente, sem chave literal nova.

### Capitu (`twitsearch`) — publicar depois do Gestão
- [x] 19. `core/hash_projeto.py`: `hash_projeto` e `token_projeto` com `indice=''` (req. 3.3)
- [x] 20. `Projeto.url_resultado`: `idx={prefix}` e token com índice quando há prefixo; link de hoje sem prefixo (req. 3.1, 3.2, 3.5)
- [x] 21. Comentário de `DS_TELEGRAM` em `telegram/models.py`; nota nos req. 1.1 e 3.2 de `projeto-resultado-gestao` apontando para esta spec
- [x] 22. Testes: substituir `test_prefixo_nao_altera_o_link` (`core/tests.py`) e as asserções de prefixo em `telegram/tests.py`; hash fixado igual ao do Gestão; compatibilidade do hash sem índice
  - Feito (20/11): `core` + `telegram` com 208 testes passando (eram 186).
- [x] 22.1. Criação de projeto (`telegram_project`) grava `prefix = PREFIXO_TELEGRAM` (`'telegram'`); testes `test_post_valido_grava_prefixo_telegram` e link do painel com `idx=telegram` (req. 3.6)
  - Feito (20/11): `core` + `telegram` com 208 testes passando.
- [ ] 23. Verificação ponta a ponta no ambiente de teste: projeto com `prefix` → "Ver resultado" → dashboard do Gestão com os documentos de `{prefix}-*` só desse projeto; link com `idx` alterado → 403

## Publicação
- [ ] 24. Deploy do Gestão (tarefas 13–18), depois do Capitu (tarefas 2–12 e 19–22), com `collectstatic` no Capitu (CSS e template novo)
- [ ] 25. Responder ao admin na #40 e na #36: o que mudou, a resposta sobre "`telegram` é o dataset (slug do `DataSource`), não o índice" e a decisão pendente sobre os dados antigos do projeto 100

## Pendências (fora desta entrega — ver "Pendências" em requirements.md)
- [ ] P1. Dados do projeto 100 que ficaram em `telegram*`: mover com `move.py` ou consultar os dois índices
- [ ] P2. `DataSource` próprio se algum prefixo for gravado em outro cluster
- [ ] P3. `GET /static/config.js` no `gestao-capitu` (CKEditor), comentário da #36
