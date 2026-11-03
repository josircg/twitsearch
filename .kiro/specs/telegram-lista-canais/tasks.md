# Tarefas — Navegação por listas de canais e mensagens do Telegram

## Antes da implementação
- [x] 0. Aprovar com o usuário o protótipo do Claude Design e as decisões abertas (local do botão, regra de acesso ao canal, semântica do filtro por termo)

## Implementação
- [x] 1. Extrair `listas_visiveis(user)` em `telegram/forms.py` e usá-lo em `TelegramProjectForm` (req. 3.1)
- [x] 2. Criar view `lista_canais` com seleção por `?lista=`, validação contra as listas visíveis, grid distinto, ordenação e paginação (req. 2, 3, 4)
- [x] 3. Criar `templates/lista_canais.html` e `templates/_paginacao.html` com tags, estados vazios e layout em cartões no mobile (req. 3, 4)
- [x] 4. Registrar rotas `telegram/listas/` e `telegram/canais/<int:pk>/` em `core/urls.py` (req. 2)
- [x] 5. Adicionar o botão "Listas de Canais" em `templates/painel.html` (req. 1)
- [x] 6. Criar `telegram/datalake.py` com `busca_mensagens` (SQL parametrizado, filtros de canal/período/termo, total + página) (req. 5.6, 5.7, 5.10)
- [x] 7. Criar o índice `idx_telegram_canal_data` (e a função `IMMUTABLE`, se necessária) em `docker/postgres-init/01_datalake.sql` e `data/datalake.sql`; validar no PostgreSQL do docker (Pendência 3)
- [x] 8. Criar `FiltroMensagensForm` e a view `canal_mensagens` com checagem de permissão, estado não sincronizado e tratamento de erro do datalake (req. 5)
- [x] 9. Criar `templates/canal_mensagens.html` com cabeçalho, filtros, destaque do termo e links `t.me` (req. 5)
- [x] 9.1. Paginação no servidor das mensagens: `PaginaMensagens`, `por_pagina` 25/50/100, navegação compacta no topo e completa no rodapé com "Ir para a página", versão celular (req. 6)
- [x] 10. Estilos em `core/static/css/style.css` escopados em `#telegram-canais`, seguindo o protótipo aprovado
- [x] 11. Escrever testes em `telegram/tests.py` conforme o design
- [ ] 12. Verificação manual no navegador (desktop e celular), com o datalake do docker populado
  - Feito (31/10): `busca_mensagens` validada contra o PostgreSQL do docker com 60 mensagens de teste, removidas depois (total, paginação, período, ILIKE sem diferenciar maiúsculas, escape de `%`/`_`, termo malicioso); `EXPLAIN` usa `idx_telegram_canal_data`.
  - Feito: conferência visual contra o protótipo (Chrome headless, 1280px e 390px) das telas de listas, mensagens, vazio/erro e paginação.
  - Pendente: teste manual com navegação real e o datalake populado.

## Edição do projeto (req. 7)
- [x] 13. Aprovar com o usuário a tela "Editar projeto" do protótipo e a regra de termos (identidade por texto, removidos interrompidos)
- [x] 14. `TelegramProjectForm` com `projeto=None`: lista atual no queryset (req. 7.5, 7.6)
- [x] 15. View `editar_projeto` + `sincroniza_termos` e rota `telegram/projetos/<int:pk>/editar/` (req. 7.2, 7.3, 7.7–7.10)
- [x] 16. `telegram_project.html` condicional ao modo edição (título, link "Meus projetos", aviso dos termos, "Salvar alterações") (req. 7.4, 7.11)
- [x] 17. Painel: nome do projeto como link para edição quando tem a rede Telegram; `prefetch_related('redes')` (req. 7.1)
- [x] 18. Testes da edição conforme o design
- [ ] 19. Conferência visual contra o protótipo (1280px e 390px)
  - Feito (31/10): telas renderizadas pelas views reais (SQLite, Chrome headless) em 1280px e 390px, com e sem erros, e painel com e sem link.
  - Pendente: teste manual com navegação real.

## Importar lista na edição, validação no navegador e rotas REST (req. 8–10)
- [x] 20. Importação com `?projeto=`: `projeto_editavel`, "Voltar" e redirect para a edição com `?lista=`; edição aceita `?lista=` (req. 8.1–8.4)
- [x] 21. Confirmação ao sair para importar com o formulário alterado (req. 8.5)
- [x] 22. `core/static/js/telegram_project.js`: validação ao vivo, alerta, botão bloqueado, foco no primeiro erro (req. 9)
- [x] 23. Template e CSS: `id` nos erros do servidor, `.is-invalido`, alerta nos dois modos, `.is-bloqueado` (req. 9.3, 9.4, 9.6)
- [x] 24. Rotas REST em `core/urls.py` com redirects 301 das antigas; `reverse()` no admin (req. 10)
- [x] 25. Testes: importação com e sem `projeto`, `?lista=` na edição, redirects das rotas antigas
- [x] 26. Conferência no navegador (Chrome headless): erros ao vivo, botão bloqueado, foco, confirmação de saída, 1280px e 390px

## Tipografia (req. 11)
- [x] 27. Registrar os pontos de decisão do req. 11 (seguidos na implementação; revisáveis pelo usuário): versão atual do protótipo publicado, line-height 1.5 nos títulos (inclui o `.pn-titulo`, hoje 1.2), rádios em 15px e os desvios aceitos (selo de status do painel, rodapé de paginação da lista em 14px)
- [x] 28. Templates: título de criação (`telegram_project.html`) e de importação (`importar_lista.html`) de `<h4 class="mb-4">` para `<h1 class="tp-titulo">`; erro de `form.publica` com `tp-erro` (req. 11.2, 11.3)
- [x] 29. CSS `#telegram-project`: `color` na regra raiz; `.form-label` 14px; `.form-control`/`.form-select` 15px com `min-height: 46px`; `textarea[name="termos"]` com line-height 1.6; `.form-check-label` 15px; `.form-text` 13px; `.alert` 14px; `.btn-import` 14px; `.btn-start` 15px com `min-height: 46px`; `.btn-cancel` 15px; `.tp-titulo` line-height 1.5 (req. 11.3, 11.12)
- [x] 30. CSS `#painel`: `.pn-titulo` e `.pn-btn` com line-height 1.5; nome de projeto sem link em `#4D4D4D` (req. 11.2, 11.4)
- [x] 31. CSS `#telegram-canais`: line-height 1.5 nos `h1` (`.tc-head h1`, `.tc-canal-nome h1`); `strong` em 600 só em `.tc-total` e `.tc-resumo-busca` (req. 11.2, 11.7)
- [x] 32. CSS `#telegram-canais` no celular (`max-width: 767.98px`): data da mensagem com peso 400 e `--medium-gray`; `.tc-status` 11px; `.tc-btn-ir` 13px (req. 11.5, 11.6)
- [x] 33. Testes em `telegram/tests.py`: criação e importação renderizam um único `<h1 class="tp-titulo">` e nenhum `<h4>`; edição continua com `<h1 class="tp-titulo">`; o erro de `publica` usa `tp-erro`
  - Feito (31/10): `TituloTipografiaTests` (2 testes); suíte do app `telegram` com 128 testes passando.
- [x] 34. Conferência de `getComputedStyle` (Chrome headless, 1280px e 390px) das seis telas contra as tabelas do req. 11; só os desvios aceitos (req. 11.9) podem restar
  - Feito (31/10): 94 papéis no desktop e 72 no celular comparados com o protótipo (`getComputedStyle`, Chrome headless, 1280px e 390px). Restam só os desvios aceitos do req. 11.9: selo de status do painel (12px / 500 contra 14px / 400), rodapé de paginação da lista (14px contra 13px) e o subtítulo de edição (conteúdo, não implementado). Também conferidos: `.alert` (14px), erro de `publica` (13px / `#B42318`) e rádios (15px / `#1E1D30`).
- [x] 35. Conferir efeitos colaterais: altura de 46px em campos e botões do formulário, ausência de rolagem horizontal em 390px (inclui a linha de data e métricas das mensagens com visualizações de 6 dígitos) e nenhuma mudança visual em início, admin e login
  - Feito (31/10): `input`, `select` e botão primário com 46px nas três telas de formulário (1280px e 390px); `scrollWidth` igual a `clientWidth` em todas as telas em 390px; início e login do admin com `getComputedStyle` idêntico ao do `style.css` anterior (HEAD). Ajuste extra: `input[type="date"]` media 48px (mínimo interno do Chrome, já era assim antes) e recebeu `height: 46px` em `#telegram-project`; o ícone de calendário não é cortado.
- [x] 37. Links de voltar `.tc-back` ("Meus projetos" e "Voltar às listas") em azul `#0066FF`/500, hover `#0052CC`, no CSS e no protótipo (req. 11.13)
- [ ] 36. Publicar o CSS: rodar `collectstatic` no deploy e confirmar que o navegador não serve o `style.css` antigo

## Pendências (fora desta entrega — ver "Pendências" em requirements.md)
- [ ] P1. Atualizar `num_participantes` periodicamente e salvar `num_mensagens` a cada lote em `get_messages`
- [ ] P2. Aplicar índice do datalake em produção
- [ ] P3. Suportar `AND`/`OR` no filtro por termo
- [ ] P4. Paginação por cursor (keyset) se algum canal passar de ~100 mil mensagens coletadas
