# Tarefas — Navegação por listas de canais e mensagens do Telegram

## Antes da implementação
- [x] 0. Aprovar com o usuário o protótipo do Claude Design e as decisões abertas (local do botão, regra de acesso ao canal, semântica do filtro por termo)

## Implementação
- [x] 1. Extrair `listas_visiveis(user)` em `telegram/forms.py` e usá-lo em `TelegramProjectForm` (req. 3.1)
- [x] 2. Criar view `lista_canais` com seleção por `?lista=`, validação contra as listas visíveis, grid distinto, ordenação e paginação (req. 2, 3, 4)
- [x] 3. Criar `templates/lista_canais.html` e `templates/_paginacao.html` com tags, estados vazios e layout em cartões no mobile (req. 3, 4)
- [x] 4. Registrar rotas `telegram/lista_canais/` e `telegram/canal/<int:pk>/` em `core/urls.py` (req. 2)
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

## Pendências (fora desta entrega — ver "Pendências" em requirements.md)
- [ ] P1. Atualizar `num_participantes` periodicamente e salvar `num_mensagens` a cada lote em `get_messages`
- [ ] P2. Aplicar índice do datalake em produção
- [ ] P3. Suportar `AND`/`OR` no filtro por termo
- [ ] P4. Paginação por cursor (keyset) se algum canal passar de ~100 mil mensagens coletadas
