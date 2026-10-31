# Design — Navegação por listas de canais e mensagens do Telegram

## Visão geral
Duas views baseadas em função em `telegram/views.py`, protegidas por `login_required(login_url='/admin/login/')`, renderizadas no servidor (sem JS adicional: `base.html` carrega apenas o bundle do Bootstrap). A seleção de listas e os filtros ficam na query string (GET).

- `lista_canais` consulta o MySQL (ORM) — `Lista` e `Canal`.
- `canal_mensagens` consulta o `Canal` no ORM e as mensagens no datalake PostgreSQL (`pg_baoba`, tabela `telegram`, coluna `source jsonb`), via `connect_postgresql`.

Protótipo visual (Claude Design): https://claude.ai/artifact/MFVvasjD7cU8ZZ8gdurZ4r — ver seção "Protótipo".

## Componentes
| Arquivo | Alteração |
|---|---|
| `telegram/datalake.py` (novo) | `busca_mensagens(channel_id, dt_inicio, dt_final, termo, limit, offset) -> (total, mensagens)`; SQL parametrizado, conexão fechada em `finally` |
| `telegram/forms.py` | `listas_visiveis(user)` (queryset compartilhado com `TelegramProjectForm`); `FiltroMensagensForm` (`dt_inicio`, `dt_final`, `termo`) com validação de datas |
| `telegram/views.py` | Views `lista_canais(request)` e `canal_mensagens(request, pk)` |
| `core/urls.py` | `path('telegram/lista_canais/', lista_canais, name='lista_canais')` e `path('telegram/canal/<int:pk>/', canal_mensagens, name='canal_mensagens')` |
| `templates/lista_canais.html` (novo) | Tags de listas + grid paginado, seção `#telegram-canais` |
| `templates/canal_mensagens.html` (novo) | Cabeçalho do canal, filtros e lista de mensagens, seção `#telegram-canais` |
| `templates/_paginacao.html` (novo) | Paginação reutilizável que preserva a query string |
| `templates/painel.html` | Botão "Listas de Canais" |
| `core/static/css/style.css` (fonte versionada; `static/` é saída do `collectstatic` e está no `.gitignore`) | Estilos escopados em `#telegram-canais` (tags, grid, cartões de mensagem), reaproveitando os tokens de `#telegram-project` |
| `docker/postgres-init/01_datalake.sql`, `data/datalake.sql` | Índice por canal + data na tabela `telegram` |
| `telegram/tests.py` | Testes das duas views |

## Decisões

### Listas visíveis e seleção
- **Queryset único:** `listas_visiveis(user) = Lista.objects.filter(Q(publica=True) | Q(dono=user)).order_by('nome')`, extraído de `TelegramProjectForm.__init__` para não divergir. Anotado com `Count('canais')` para o total exibido na tag (evita N+1 de `tot_canais`).
- **Seleção:** `request.GET.getlist('lista')` → filtra ids numéricos → interseção com `listas_visiveis(user)`. Ids inválidos ou de listas privadas alheias são descartados (req. 3.5). Isso também impede ver canais de lista privada alheia pela URL.
- **Toggle sem JS:** cada tag é um `<a>` cujo `href` é a query string atual com o id adicionado/removido (montado na view: lista de `{lista, selecionada, url}`). Acessível por teclado, com `aria-pressed`.

### Grid
- `Canal.objects.filter(lista__in=selecionadas).distinct().order_by('-num_participantes', 'username')`.
- `Paginator(qs, 50)`; `_paginacao.html` recebe a query string sem `page` para preservar `lista=` (e, na tela do canal, os filtros).
- `sobre` truncado com `truncatechars:160` e `title` com o texto completo.
- Números com `{% load humanize %}` / `intcomma` (verificar `django.contrib.humanize` em `INSTALLED_APPS`; caso ausente, adicionar) — com `USE_THOUSAND_SEPARATOR` ou filtro próprio para garantir o ponto como separador pt-BR.
- **Mobile:** abaixo de 576px a tabela vira lista de cartões (canal + descrição em 2 linhas + participantes e mensagens lado a lado), evitando scroll horizontal.

### Origem dos números
Nenhum total do cabeçalho vem do datalake; todos são campos de `telegram.Canal` (MySQL):

| Rótulo | Campo | Atualizado por |
|---|---|---|
| Participantes | `num_participantes` | `sync_channels` (`participants_count` da API), uma única vez na sincronização |
| Mensagens coletadas | `num_mensagens` | `get_messages`, somando o que capturou em cada execução (desde `DATA_LIMITE`) |
| Última coleta | `dt_ultima_carga` | `get_messages`, ao fim de cada execução no canal (mesmo sem mensagens novas) |

O único número vindo do datalake é o total da lista de mensagens com os filtros aplicados (`count(*)` da paginação). Não exibimos "total do canal no Telegram": esse dado não é coletado.

### Página do canal
- **Permissão:** `get_object_or_404(Canal.objects.filter(lista__in=listas_visiveis(user)).distinct(), pk=pk)` (req. 5.2).
- **Voltar às listas:** o link do grid inclui `?voltar=<query string codificada>`; a view só aceita valores que comecem com `lista=` (evita open redirect) e, sem ele, aponta para `lista_canais` sem seleção.
- **Sem `id_numerico`:** não consulta o datalake; template mostra o estado "não sincronizado" (req. 5.12).
- **Datas:** `DateField` → `timezone.make_aware(datetime.combine(d, time.min / time.max))` no fuso `America/Sao_Paulo`, mesma regra de `telegram_project`.
- **Termo:** strip; máx. 200 caracteres. Na consulta, `ILIKE` com `%`, `_` e `\` escapados. Destaque no template com filtro próprio que escapa o texto e envolve as ocorrências em `<mark>` (case-insensitive), retornando `mark_safe` só depois do escape.
- **Erro do datalake:** `busca_mensagens` deixa a exceção subir; a view captura `psycopg.Error`/`Exception` da conexão, registra com `logger.exception` e renderiza o template com `erro_datalake=True` (req. 5.14).

### Consulta ao datalake (`telegram/datalake.py`)
```sql
-- total
SELECT count(*) FROM telegram
 WHERE (source->>'channel_id')::bigint = %(canal)s
   AND (%(ini)s::timestamptz IS NULL OR telegram_ts(source->>'timestamp') >= %(ini)s)
   AND (%(fim)s::timestamptz IS NULL OR telegram_ts(source->>'timestamp') <= %(fim)s)
   AND (%(termo)s::text IS NULL OR source->>'message' ILIKE %(termo)s ESCAPE '\');

-- página
SELECT source FROM telegram WHERE <mesmos filtros>
 ORDER BY telegram_ts(source->>'timestamp') DESC, (source->>'message_id')::bigint DESC
 LIMIT %(limit)s OFFSET %(offset)s;
```
A expressão `telegram_ts(source->>'timestamp')` precisa ser idêntica no índice, no `WHERE` e no `ORDER BY` para o planner usar o índice.
- Sempre parâmetros nomeados (`psycopg`), nunca f-string com valores do usuário. A tabela `telegram` é constante do módulo (mesmo nome usado em `export_telegram.TABELA`).
- O filtro por canal usa `channel_id` (= `Canal.id_numerico`), que está em todos os documentos gravados por `serializa_mensagem`.
- `timestamp` é ISO 8601 com offset (`message.date.isoformat()`); comparar por cast `::timestamptz`, não por string.
- Retorna dicionários com `timestamp` já convertido para `datetime` aware, `message`, `message_id`, `views`, `forwards`, `media_type`, `username`.
- Conexão aberta por requisição e fechada em `finally` (volume baixo, uso interativo; pool fica para depois).

### Paginação das mensagens (req. 6)
- **Não usar o `Paginator` do Django** sobre a lista inteira: ele exigiria trazer todas as mensagens do PostgreSQL. A view calcula `offset = (page - 1) * por_pagina` e `busca_mensagens` executa duas consultas na mesma conexão: `count(*)` com os filtros (total) e a página com `LIMIT/OFFSET`.
- A página é ajustada depois do `count`: se `page > última`, refaz a busca da última página (evita página vazia por URL antiga).
- `por_pagina` ∈ {25, 50, 100} (padrão 25 — mensagens são textos longos; 25 mantém a página leve). Valores fora da lista caem no padrão; isso também limita o `LIMIT` enviado ao banco.
- Um objeto simples `PaginaMensagens(page, por_pagina, total)` expõe `num_paginas`, `inicio`, `fim`, `tem_anterior`, `tem_proxima` e `paginas_visiveis()` (1, última, atual ± 1, com `None` como reticências) para o template.
- `_paginacao.html` recebe a query string sem `page` (`request.GET.copy()` → `pop('page')` → `urlencode()`) e é usado acima (versão compacta) e abaixo da lista (versão completa). "Ir para a página" é um mini-formulário GET que reenvia os filtros como campos ocultos.
- O formulário de filtros não envia `page`, então filtrar sempre volta à página 1 (req. 6.7); o seletor "Por página" faz parte do mesmo formulário e envia ao mudar (`onchange="this.form.submit()"`, com botão "Filtrar" como fallback sem JS).
- **Desempenho:** com o índice `idx_telegram_canal_data`, `count(*)` e `OFFSET` ficam baratos na casa de milhares a dezenas de milhares de mensagens por canal. Se algum canal passar de ~100 mil mensagens, trocar páginas profundas por paginação por cursor (keyset: `WHERE telegram_ts(...) < :ultimo_ts`) — registrado como pendência.

### Índice no datalake
```sql
-- O timestamp é sempre ISO 8601 com offset explícito (isoformat() de datetime aware),
-- então o resultado não depende de DateStyle/TimeZone e a função pode ser IMMUTABLE.
CREATE OR REPLACE FUNCTION telegram_ts(text) RETURNS timestamptz
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    AS $$ SELECT $1::timestamptz $$;

CREATE INDEX IF NOT EXISTS idx_telegram_canal_data
    ON telegram (((source->>'channel_id')::bigint), telegram_ts(source->>'timestamp'));
```
- O cast direto `::timestamptz` não é `IMMUTABLE` no PostgreSQL e seria recusado em um índice; por isso a função wrapper, usada no índice e na consulta. Validar no PostgreSQL do docker antes de fechar.
- Aplicar manualmente em produção (tabela externa, `UNLOGGED`, fora das migrations).
- O filtro por termo (`ILIKE '%x%'`) não usa índice; com o filtro por canal primeiro, o volume por canal é aceitável. `pg_trgm` fica como evolução.

## Modelo de dados
Sem migrações no Django. Usa `telegram.Lista`, `telegram.Canal` (ORM) e a tabela `telegram` do datalake (somente leitura).

## Protótipo
Protótipo navegável gerado no Claude Design com a identidade do Capitu (Poppins, `--blue #0066FF`, cartões brancos `#E3E8EF` raio 16px, botões pílula raio 30px):

- Link: https://claude.ai/artifact/MFVvasjD7cU8ZZ8gdurZ4r (privado; compartilhar pelo menu Share)
- Telas: painel com o novo botão; listas de canais (sem seleção, uma lista, várias listas, lista vazia — tweak "selecaoInicial"); página do canal (com resultados, sem resultado, canal não sincronizado, datalake indisponível — tweak "estado"; termo e datas são interativos, incluindo o erro de data final < inicial); versões em largura de celular (390px).
- No celular as datas aparecem como texto `dd/mm/aaaa` só para leitura no mock; na implementação usar `<input type="date">` nativo.
- **Itens ilustrativos (fora das tarefas, a menos que aprovados):**
  1. Painel redesenhado (botões pílula, tabela em cartão, "Listas de Canais" em contorno): a tarefa 5 só adiciona o botão à barra Bootstrap existente.
  2. Filtro por termo enquanto digita: o design especifica formulário GET enviado por "Filtrar".
- Mensagens em lista compacta (ajuste pedido em comentário no protótipo: margens largas demais).
- A tela de mensagens simula um canal com 4.870 mensagens coletadas (tweak "totalColetadas"); a paginação é navegável no Play (anterior/próxima, números, "Ir para a página", 25/50/100 por página).
- O cabeçalho do protótipo reproduz o menu atual de `base.html` (logo `static/img/logo.svg`, Início, Como funciona, Como ter acesso, Institucional, "Acessar Sistema"); no celular, logo + botão de menu, como o `navbar-expand-lg` do Bootstrap.

## Testes (`telegram/tests.py`)
`TestCase` padrão do Django (como os testes existentes). `connect_postgresql` mockado com `unittest.mock.patch('telegram.datalake.connect_postgresql')`.

- Anônimo em `lista_canais` e `canal_mensagens` → 302 para `/admin/login/`.
- Tags: exibe públicas e próprias privadas; não exibe privadas de outro usuário.
- `?lista=` com id de lista privada alheia → ignorado, nenhum canal dela no grid.
- Sem seleção → mensagem de orientação, sem grid.
- Duas listas com canal em comum → canal aparece uma vez; total correto.
- Ordenação por participantes e paginação preservando `lista=`.
- Link de mensagens aponta para `/telegram/canal/<pk>/`.
- Painel exibe o botão "Listas de Canais" apontando para `/telegram/lista_canais/`.
- Canal fora de qualquer lista visível → 404.
- Canal sem `id_numerico` → estado "não sincronizado" e `connect_postgresql` não chamado.
- Data final < inicial → erro no campo, `connect_postgresql` não chamado.
- Filtros repassados à consulta: canal = `id_numerico`, datas no fuso local com fim do dia, termo com `%`/`_` escapados.
- Datalake indisponível (mock levanta exceção) → 200 com mensagem amigável.
- Mensagem com `message=None` → "[mídia sem texto]"; termo destacado em `<mark>` sem permitir HTML injetado no texto.
- `datalake.busca_mensagens`: SQL parametrizado (nenhum valor do usuário interpolado na string) e conexão fechada mesmo com erro.
- Paginação: `page=3&por_pagina=25` repassa `LIMIT 25 OFFSET 50`; `por_pagina=500` cai para 25; `page=abc`/`page=0` → página 1; `page` acima da última → última página; links de página preservam `termo`, datas e `por_pagina`; "Anterior" desabilitado na página 1 e "Próxima" na última; `PaginaMensagens.paginas_visiveis()` com reticências (ex.: página 50 de 195 → 1 … 49 50 51 … 195).
