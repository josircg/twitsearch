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
| `core/urls.py` | `path('telegram/listas/', lista_canais, name='lista_canais')` e `path('telegram/canais/<int:pk>/', canal_mensagens, name='canal_mensagens')` |
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

### Edição do projeto (req. 7)
| Arquivo | Alteração |
|---|---|
| `telegram/forms.py` | `TelegramProjectForm` ganha `projeto=None`; com projeto, soma a lista atual ao queryset (`listas_visiveis(user) \| Lista.objects.filter(pk=projeto.lista_canais_id)`) |
| `telegram/views.py` | View `editar_projeto(request, pk)`; a gravação dos termos fica numa função `sincroniza_termos(projeto, termos, dtinicio, dtfinal, rede)` para ser testada isoladamente |
| `core/urls.py` | `path('telegram/projetos/<int:pk>/editar/', editar_projeto, name='editar_projeto')`, ao lado de `telegram/projetos/novo/` |
| `templates/telegram_project.html` | Reaproveitado: título, botão e campo `status` condicionais a `projeto` (sem template novo) |
| `templates/painel.html` | Nome do projeto vira link quando o projeto tem a rede Telegram |
| `core/views.py` (`painel`) | `prefetch_related('redes')` para saber, sem N+1, quais projetos têm Telegram |

- **Permissão:** `get_object_or_404(Projeto, pk=pk, usuario=request.user, redes__nome__iexact='Telegram')`. A rede é localizada por nome, como em `telegram_project` (Pendência 3 de `telegram-projeto`).
- **Valores iniciais:** termos ativos = `projeto.termo_set.exclude(status='X').order_by('pk')`. `dt_inicio = localtime(min(dtinicio)).date()` e `dt_final = localtime(max(dtfinal)).date()`. `dtfinal` pode ser nulo em projetos antigos: nesse caso o campo vem vazio e o formulário exige preenchimento ao salvar.
- **Termos por texto, não por posição:** o textarea não carrega ids, então a identidade do termo é o texto da linha (após `strip`). Editar uma letra de um termo equivale a interromper o antigo e criar um novo. Isso evita que uma reordenação de linhas troque o histórico de coleta entre termos.
- **Interromper em vez de excluir:** `Termo.projeto` é `PROTECT` e há tweets, contagens e ponteiros ligados ao termo. Interrompido (`'X'`) já existe em `STATUS_TERMO` e não é processado pela coleta.
- **Datas em todos os termos ativos:** o projeto não tem período próprio; o período é dos termos. Ao salvar, `dtinicio`/`dtfinal` são regravados nos termos ativos (mantidos, reativados e novos). Termos interrompidos mantêm o período que tinham.
- **Sem Status e sem link de resumo:** removidos da tela a pedido do usuário (comentários no protótipo, 31/10). O `status` do projeto continua sendo alterado só pelo admin.
- **Template:** o mesmo `telegram_project.html` com `{% if projeto %}`: título "Editar projeto", link "Meus projetos" de volta ao painel e botão "Salvar alterações". Evita duas cópias do formulário.
- **Painel:** a linha inteira não é clicável (sem JS); o nome é o link, com ícone de lápis e `aria-label="Editar projeto <nome>"`.

### Importar lista a partir da edição (req. 8)
- `telegram/views.py`: função `projeto_editavel(user, pk)` → `Projeto | None`, com o mesmo filtro de `editar_projeto` (dono + rede Telegram), reaproveitada pelas duas views. `pk` não numérico → `None`.
- `importar_lista` lê `request.GET.get('projeto')`. O formulário não tem `action`, então o POST vai para a mesma URL e mantém a query string. Com projeto válido, o contexto ganha `voltar_url = reverse('editar_projeto', args=[pk])` e o redirect final vai para `{editar_projeto}?lista=<nova>`. Sem projeto, `voltar_url = reverse('telegram_project')` e o fluxo continua como hoje.
- `importar_lista.html`: o link "Voltar" usa `{{ voltar_url }}`.
- `editar_projeto` (GET): `initial['lista'] = request.GET['lista']` quando o id é um `pk` do queryset do campo (`form.fields['lista'].queryset.filter(pk=...)`); senão mantém `projeto.lista_canais_id`.
- `telegram_project.html`: em modo edição, `href="{% url 'importar_lista' %}?projeto={{ projeto.pk }}"`, com `data-confirma-saida` para o JS do req. 9 pedir confirmação quando o formulário estiver alterado (`confirm()` nativo, comparando os valores atuais com os do carregamento).

### Validação no navegador (req. 9)
- **Arquivo:** `core/static/js/telegram_project.js`, carregado no `{% block scripts %}` de `telegram_project.html` com `{% static %}` e `defer`. Sem dependências e sem build. JS puro (ES2017), escopado em `#telegram-project form`.
- **Regras:** espelham `TelegramProjectForm` (obrigatórios; `dt_final >= dt_inicio`; termos: `splitlines`, `strip`, ignora linhas vazias, ≥ 1 termo, ≤ 2000 caracteres, `AND`/`OR` só em maiúsculas, não no início, no fim nem consecutivos). As mensagens ficam num objeto no topo do arquivo, com os mesmos textos do servidor. Os testes do servidor continuam sendo a fonte da verdade.
- **Marcação dos erros:** o JS cria ou reaproveita, logo após o campo (depois do `form-text`, se houver), um `<div class="text-danger tp-erro" id="erro_<campo>">`. Os erros vindos do servidor também passam a ter esse `id` em `_telegram_field.html`, para o JS achá-los e removê-los quando o campo for corrigido. `aria-invalid` e `aria-describedby` são atualizados no `input`, `select` ou `textarea`.
- **Alerta e botão:** o alerta `.tp-alerta` passa a ser renderizado nos dois modos, oculto (`hidden`) quando não há erros do servidor. O JS mostra ou esconde o alerta e alterna `aria-disabled` e a classe `.is-bloqueado` no `.btn-start`. Não usa o atributo `disabled`, para o clique continuar chegando ao handler (req. 9.5). O `submit` é cancelado com `preventDefault()` enquanto houver erro.
- **Campos tocados:** um `Set` marca o campo no primeiro `input`/`change`/`blur`. Um envio marca todos. Campos com erro do servidor já começam marcados.
- **Borda vermelha:** troca da regra `:has(~ .text-danger)` por uma classe explícita `.is-invalido` (aplicada pelo template quando `field.errors` e pelo JS), o que funciona nos dois modos e em navegadores sem `:has`.

### Rotas REST (req. 10)
- `core/urls.py`: os `path()` novos, com os mesmos `name=`. Os antigos viram `RedirectView.as_view(pattern_name=<nome>, permanent=True, query_string=True)` — quem tem `<int:pk>` repassa o kwarg —, todos agrupados num bloco comentado "rotas antigas (redirecionam)".
- Ordem: `telegram/canais/importar/` antes de `telegram/canais/<int:pk>/` (não conflitam por causa do conversor `int`, mas a leitura fica mais clara).
- `core/admin.py`: `'/termo_stat/%d' % object_id` → `reverse('status_coleta', args=[object_id])`. A nova rota mantém o parâmetro `termo_id`.
- Testes que usam caminhos literais passam a usar `reverse()`, mais um teste de redirecionamento por rota antiga (status 301, `Location` com a query string).
- Fora: `/api/...` (contrato com o `vtrack-consumidor` e outros) e as ações/downloads do Twitter listadas em "Fora de escopo".

### Tipografia (req. 11)
**Método da medição (31/10/2026).** Cada tela foi renderizada pela view real (SQLite, datalake mockado), em cópia com um script que coleta `getComputedStyle` de todos os elementos com texto, no Chrome headless em 1280px e em 390px (iframe). O protótipo foi convertido do mesmo jeito (artboards sem `{{ }}` nem `sc-if`/`sc-for`), e os papéis foram pareados por texto. Resultado: 94 papéis comparados, 34 com diferença contra o protótipo correto, dos quais 3 viraram desvios aceitos (req. 11.9); o restante está nas tabelas do req. 11. Família: sem diferença (Poppins em tudo, inclusive campos e botões, por causa do `font-family: inherit` do reboot do Bootstrap).

**Qual protótipo vale.** A versão atual do protótipo publicado. As telas `Main`, `Canal`, `ListaMobile` e `CanalMobile` tiveram uma versão anterior à lista compacta (mensagens em cartões de 15px/1.65, "Total no Telegram"); o CSS de `#telegram-canais` já segue a atual, então comparar com a antiga produziria falsas diferenças (mensagem 14px→15px, data 12px→13px etc.) e NÃO deve ser feito.

**Decisão: regras por bloco, sem tokens globais.** Cada alteração entra nos blocos já escopados (`#painel` / `pn-`, `#telegram-project` / `tp-`, `#telegram-canais` / `tc-`), com valores literais, como o restante do arquivo. Não criar `:root { --fs-… }` nem classes utilitárias (`.fs-14`, `.t-label`): a escala é curta, muda por tela (15px só nos campos do formulário, 14px nas demais telas, 13px/12px/11px no celular) e os blocos já declaram seus tokens localmente (`--field-border`, `--tc-borda`). Tokens globais convidariam o reaproveitamento em início, admin e login, fora do escopo. Também não criar regra global de `h1` ou `strong`.

**Causas (padrões do Bootstrap 5.3 que o protótipo não tem):**
| Padrão do Bootstrap | Efeito observado |
|---|---|
| `h1…h6 { line-height: 1.2; color: var(--bs-heading-color) }` | títulos com 1.2 em vez de ~1.5 e cor `#212529` onde o bloco não define cor (`.tp-titulo`) |
| `h4` com tamanho responsivo (RFS) | título de criação e importação: 24px no desktop, 21,57px no celular, peso 500 |
| `strong { font-weight: bolder }` | 700 onde o protótipo usa 600 (`strong` do total) |
| `.form-control`, `.form-select`, `.form-check-label`, `.alert` em `1rem` | campos, rádios e mensagens com 16px (protótipo: 15px e 14px) |
| `.form-text { font-size: .875em }` | ajuda com 14px (protótipo: 13px) |
| `.text-danger` sem `tp-erro` | erro de Visibilidade com 16px e `#dc3545` |
| `body { color: #212529 }` | texto sem cor própria dentro de `#telegram-project` (o bloco não define `color`, ao contrário de `#painel` e `#telegram-canais`) |

**Alterações em `core/static/css/style.css`** (valores no req. 11):
| Bloco / seletor | Mudança |
|---|---|
| `#telegram-project` (regra raiz, onde estão `--field-border` e `--field-icon`) | acrescentar `color: var(--dark-gray);` — corrige o título e o rótulo dos rádios |
| `#telegram-project .form-label` | `font-size: 14px` |
| `#telegram-project .form-control`, `.form-select` | `font-size: 15px` e `min-height: 46px` (a redução de 16px para 15px tiraria ~1,5px da altura; o protótipo tem 46px) |
| `#telegram-project textarea[name="termos"]` (novo) | `line-height: 1.6` |
| `#telegram-project .form-check-label` (novo) | `font-size: 15px` |
| `#telegram-project .form-text` | `font-size: 13px` (a regra existente só define a cor) |
| `#telegram-project .alert` (novo) | `font-size: 14px` |
| `#telegram-project .btn-import` | `font-size: 14px` (hoje `0.9rem` = 14,4px) |
| `#telegram-project .btn-start` | `font-size: 15px` e `min-height: 46px` |
| `#telegram-project .btn-cancel` | `font-size: 15px` (o `.tp-edicao .btn-cancel` mantém `min-height: 44px`) |
| `#telegram-project .tp-titulo` | `line-height: 1.5` (tamanho 24px, peso 600 e margem já estão certos) |
| `#painel .pn-titulo` | `line-height: 1.5` (hoje 1.2 explícito) |
| `#painel .pn-btn` | `line-height: 1.5` (hoje 1.4; a altura continua dada por `min-height: 44px`) |
| `#painel .pn-tabela td.pn-nome:not(.pn-nome-link)` (novo) | `color: #4D4D4D` |
| `#telegram-canais .tc-head h1`, `.tc-canal-nome h1` | `line-height: 1.5` (os tamanhos 26/22/21px já estão certos) |
| `#telegram-canais .tc-total strong`, `.tc-resumo-busca strong` (novo) | `font-weight: 600`; NÃO usar `#telegram-canais strong`, porque `.tc-mini-status strong` ("Página **3** de …") é 700 no protótipo e `.tc-faixa strong` já tem 600 próprio |
| `@media (max-width: 767.98px)`: `.tc-msg-meta time` (novo) | `font-weight: 400; color: var(--medium-gray)` (no desktop continua 500 e `--tc-texto-2`) |
| `@media (max-width: 767.98px)`: `.tc-status` (novo) | `font-size: 11px` |
| `@media (max-width: 767.98px)`: `.tc-btn-ir` (novo) | `font-size: 13px` |

**Alterações em templates:**
| Arquivo | Mudança |
|---|---|
| `templates/telegram_project.html` | no modo criação, `<h4 class="mb-4">Nova coleta Telegram</h4>` → `<h1 class="tp-titulo">Nova coleta Telegram</h1>` (a margem de 24px do `.tp-titulo` equivale ao `mb-4`) |
| `templates/importar_lista.html` | `<h4 class="mb-4">` → `<h1 class="tp-titulo">`; o erro de `form.publica` passa de `class="text-danger"` para `class="text-danger tp-erro"` (mesmo 13px / `#B42318` dos demais erros) |

**Riscos e cuidados:**
- **Bootstrap e especificidade.** Os seletores `#telegram-project …` têm especificidade maior que as classes do Bootstrap, então vencem sem `!important`. `.alert` e `.text-danger` trazem a cor própria do Bootstrap; só o tamanho (e, no erro de rádio, a classe `tp-erro` com `!important` de cor já existente) é alterado.
- **`h4` → `h1`.** As duas telas passam a ter um `h1` (hoje não têm). O cabeçalho de `base.html` não usa `h1`, então não há título duplicado. Nenhum teste existente depende da tag `h4`.
- **Cor raiz de `#telegram-project`.** Afeta só texto sem cor própria (título e rótulo dos rádios); `.form-text`, `.tp-*`, `.alert` e `.btn-*` já definem cor.
- **Altura dos campos.** `input` com 15px e padding `0.6rem` ficaria em ~44,7px; por isso o `min-height: 46px`. Em `textarea` o `min-height` é inócuo (as linhas dominam). O `input[type="date"]` do Chrome tem altura mínima interna de 48px (já era assim antes); `#telegram-project input[type="date"] { height: 46px }` o alinha aos demais campos sem cortar o ícone do calendário.
- **`.pn-titulo` com 1.2 explícito.** Foi escolha do bloco, não do Bootstrap; o protótipo renderiza ~1.5 (35px de altura de linha contra 28,8px). Se o usuário preferir o título mais compacto, trocar só o critério de line-height do painel.
- **Celular.** `.tc-msg-meta` tem `white-space: nowrap`; a linha única data + "vis." + "enc." + "Telegram ↗" já está no limite em 390px e não muda de tamanho nesta entrega (11px), mas o peso 400 da data a deixa um pouco mais estreita. Conferir mesmo assim com visualizações de 6 dígitos.
- **Fontes.** `@import` do Google Fonts no topo de `style.css` carrega os pesos 100–800; os usados nestas telas são 400, 500, 600 e 700 (mini-status), mais o 300 do botão do cabeçalho. Não alterar o `@import` nesta entrega.
- **Publicação.** `static/` é saída do `collectstatic`; sem rodá-lo (e sem limpar o cache do navegador) as telas continuam com o CSS antigo.

**Verificação.** Repetir a medição do método acima (script de `getComputedStyle` + Chrome headless, 1280px e 390px) e conferir cada linha das tabelas do req. 11; a diferença deve ficar restrita aos desvios aceitos (req. 11.9). Os testes de `telegram/tests.py` ganham dois casos: criação e importação renderizam exatamente um `<h1 class="tp-titulo">` e nenhum `<h4>`; o erro de `publica` usa `tp-erro`.

## Modelo de dados
Sem migrações no Django. Usa `telegram.Lista`, `telegram.Canal` (ORM) e a tabela `telegram` do datalake (somente leitura).

## Protótipo
Protótipo navegável gerado no Claude Design com a identidade do Capitu (Poppins, `--blue #0066FF`, cartões brancos `#E3E8EF` raio 16px, botões pílula raio 30px):

- Link: https://claude.ai/artifact/MFVvasjD7cU8ZZ8gdurZ4r (privado; compartilhar pelo menu Share)
- Telas: painel com o novo botão e os nomes dos projetos como link; edição do projeto (formulário preenchido, aviso sobre termos removidos; tweak "estado" mostra o formulário com erro); listas de canais (sem seleção, uma lista, várias listas, lista vazia — tweak "selecaoInicial"); página do canal (com resultados, sem resultado, canal não sincronizado, datalake indisponível — tweak "estado"; termo e datas são interativos, incluindo o erro de data final < inicial); versões em largura de celular (390px).
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
- Link de mensagens aponta para `/telegram/canais/<pk>/`.
- Painel exibe o botão "Listas de Canais" apontando para `/telegram/listas/`.
- Canal fora de qualquer lista visível → 404.
- Canal sem `id_numerico` → estado "não sincronizado" e `connect_postgresql` não chamado.
- Data final < inicial → erro no campo, `connect_postgresql` não chamado.
- Filtros repassados à consulta: canal = `id_numerico`, datas no fuso local com fim do dia, termo com `%`/`_` escapados.
- Datalake indisponível (mock levanta exceção) → 200 com mensagem amigável.
- Mensagem com `message=None` → "[mídia sem texto]"; termo destacado em `<mark>` sem permitir HTML injetado no texto.
- `datalake.busca_mensagens`: SQL parametrizado (nenhum valor do usuário interpolado na string) e conexão fechada mesmo com erro.
- Edição do projeto: anônimo → login; projeto de outro usuário ou sem a rede Telegram → 404; formulário vem preenchido (datas mín./máx. dos termos ativos, termos um por linha); salvar mantém termo idêntico (mesmo pk, `last_count` preservado), cria termo novo com `TermoStatus`, interrompe termo removido (sem excluir) e reativa termo que volta; datas regravadas só nos termos ativos; formulário inválido não grava nada; lista atual não visível continua selecionável; painel mostra o link só para projetos com Telegram.
- Paginação: `page=3&por_pagina=25` repassa `LIMIT 25 OFFSET 50`; `por_pagina=500` cai para 25; `page=abc`/`page=0` → página 1; `page` acima da última → última página; links de página preservam `termo`, datas e `por_pagina`; "Anterior" desabilitado na página 1 e "Próxima" na última; `PaginaMensagens.paginas_visiveis()` com reticências (ex.: página 50 de 195 → 1 … 49 50 51 … 195).
