# Design — Registro de projeto de coleta Telegram

## Visão geral
View baseada em função (`telegram_project`) em `telegram/views.py`, protegida por `login_required`, com um `forms.Form` (`TelegramProjectForm`) e template que estende `base.html`. Ao salvar, cria `Projeto` + `Termo`s + `TermoStatus` em `transaction.atomic()`, emite `messages.success` e redireciona para `painel`.

## Componentes
| Arquivo | Alteração |
|---|---|
| `telegram/forms.py` | `TelegramProjectForm`: `nome`, `objetivo` (Textarea), `lista` (ModelChoiceField), `dt_inicio`, `dt_final` (DateField), `termos` (Textarea, um por linha); `clean_termos` e `clean` (datas) |
| `telegram/views.py` | View `telegram_project(request)` |
| `core/urls.py` | `path('telegram_project/', telegram_project, name='telegram_project')` (import junto de `importacao_canais`) |
| `core/models.py` | Propriedade `Projeto.url_resumo` → `reverse('core_projeto_stats', args=[self.pk])` (sem migração) |
| `templates/telegram_project.html` | Formulário (crispy, no padrão de `importacao.html`) + botão "Importar minha própria lista" |
| `templates/painel.html` | Botão Telegram aponta para `{% url 'telegram_project' %}`; renderiza `messages` |

## Decisões
- `login_url='/admin/login/'`, igual ao `painel` (o projeto não define `LOGIN_URL`).
- **Queryset de listas:** `Lista.objects.filter(Q(publica=True) | Q(dono=user)).order_by('nome')`, montado em `__init__(user=...)`. Garante que um usuário não use lista privada alheia, também na validação (ModelChoiceField valida contra o queryset).
- **Termos:** `termos.splitlines()` → strip → descarta vazios. Validação por tokens (`split()`): primeiro/último token não pode ser `AND`/`OR`, e dois conectivos não podem ser consecutivos. Nenhuma outra sintaxe é validada.
- **Datas:** `DateField` convertido para datetime com timezone (`timezone.make_aware`) em `dtinicio`/`dtfinal`; `dtfinal` = fim do dia seria mais intuitivo (`23:59:59`) — aplicar na conversão.
- **Rede Telegram:** `Rede.objects.get(nome__iexact='Telegram')`; se não existir, a view responde com mensagem de erro e não grava (evita o `4` hardcoded).
- **Projeto.grupo** é `null=True`; fica nulo. `eixo` fica nulo.
- **Transação:** `transaction.atomic()` envolve `Projeto`, `redes.add`, `Termo` e `TermoStatus`.
- **Mensagem:** `messages.success(request, mark_safe(format_html(...)))` com `format_html('Para acompanhar o resultado da coleta, clique no link <a href="{0}">{0}</a>', projeto.url_resumo)`, evitando HTML sem escape.
- **Botão de importação:** link para `importacao_canais` (ver Pendências, item 2 dos requisitos).

## Modelo de dados
Usa `core.models.Projeto`, `Termo`, `TermoStatus`, `Rede` e `telegram.models.Lista`. Sem migrações (`url_resumo` é propriedade).

## Testes (`telegram/tests.py`)
- Anônimo em GET e POST → 302 para o login.
- GET autenticado → 200 e lista contém públicas + próprias privadas, mas não privadas de outro usuário.
- POST válido com 2 termos → 1 `Projeto`, 2 `Termo`, 2 `TermoStatus`, redirect para `/painel/`, mensagem com a `url_resumo`.
- POST com data final < inicial → 200, nada gravado.
- Termos: linhas vazias ignoradas; `ecologia AND`, `OR x` e `a AND OR b` rejeitados; `ecologia and x` aceito.
- Nome com mais de 40 caracteres rejeitado.
- Lista privada de outro usuário rejeitada.
- Falha na criação de `Termo` desfaz o `Projeto` (atomicidade).
- Painel: botão "Nova coleta Telegram" aponta para `/telegram_project/`.
