# Design — Resultado do projeto no Gestão (acesso por hash)

## Visão geral
```
Capitu (1 ambiente)                       Gestão (N ambientes)
GESTAO_URL, PROJETO_HASH_KEY              PROJETO_HASH_KEY (mesmo valor)
Projeto.prefix = 'vtrack-telegram'

/painel/ ──"Ver resultado"──▶  {GESTAO_URL}/dashboard?hash={id}-{hmac(id, ds)}&ds=vtrack-telegram
                                 │ 1. valida HMAC do par (id, ds), sem rede
                                 │ 2. session['projeto_acesso'] = id
                                 │    session['opensearch_index'] = 'vtrack-telegram'  (sem checar grupo)
                                 │ 3. 302 → /dashboard  (hash some da URL)
                                 ▼
                              /dashboard ─▶ /dataset?page=2 ─▶ /visualization/<id> ─▶ /alerts
                              (nada é reenviado: tudo é lido da sessão;
                               monitoramento_id = id forçado no cliente OpenSearch)
```

O `ds` vem do `Projeto.prefix` e entra no HMAC. Por isso o Gestão não precisa de cadastro extra para saber quais datasets aceitam o link: só o par (projeto, ds) assinado pelo Capitu é aceito.

## Capitu (`twitsearch`)

| Arquivo | Alteração |
|---|---|
| `core/hash_projeto.py` (novo) | `hash_projeto(projeto_id, ds)` e `token_projeto(projeto_id, ds)` |
| `core/models.py` | Propriedade `Projeto.url_resultado` (sem migração de esquema) |
| `telegram/models.py` | Constante `PREFIXO_TELEGRAM = 'vtrack-telegram'` |
| `telegram/views.py` | `telegram_project`: `Projeto.objects.create(..., prefix=PREFIXO_TELEGRAM)`. `editar_projeto` fica como está (`update_fields` sem `prefix`) |
| `templates/painel.html` | Coluna "Resultado" condicional (`{% if mostrar_resultado %}`); "—" quando `url_resultado` é `None` |
| `core/views.py` | `painel` passa `mostrar_resultado = bool(GESTAO_URL and PROJETO_HASH_KEY)` |
| `core/admin.py` | (Opcional) `link_resultado` em `ProjetoAdmin.list_display` |
| `doc/local.py` | Exemplo de `GESTAO_URL` e `PROJETO_HASH_KEY` |

```python
# core/hash_projeto.py
import hashlib
import hmac
from django.conf import settings

def hash_projeto(projeto_id, ds):
    msg = f'projeto:{projeto_id}:{ds}'.encode()
    return hmac.new(settings.PROJETO_HASH_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]

def token_projeto(projeto_id, ds):
    return f'{projeto_id}-{hash_projeto(projeto_id, ds)}'
```

```python
# core/models.py — Projeto
@property
def url_resultado(self):
    gestao_url = getattr(settings, 'GESTAO_URL', '')
    if not (gestao_url and getattr(settings, 'PROJETO_HASH_KEY', '') and self.prefix):
        return None
    params = urlencode({'hash': token_projeto(self.pk, self.prefix), 'ds': self.prefix})
    return f'{gestao_url.rstrip("/")}/dashboard?{params}'
```

### Projetos existentes
Não há migração de dados. O painel lista todos os projetos do usuário, de qualquer rede. Os que não têm prefixo, inclusive projetos Telegram antigos, exibem "—" na coluna "Resultado" até o prefixo ser preenchido manualmente no admin.

## Gestão (`gestao-minerva`)

| Arquivo | Alteração |
|---|---|
| `utils/hash_projeto.py` (novo) | `hash_projeto(projeto_id, ds)` e `valida_hash(token, ds) -> int \| None`: separa id e hash, recalcula com o `ds` e compara com `hmac.compare_digest` |
| `dashboards/opensearch/session.py` | `get/set/limpa_projeto_acesso`; `set_opensearch_index` ciente do modo projeto |
| `dashboards/opensearch/datasource.py` | `_get_opensearch_connection` dispensa grupo no modo projeto (só para o `ds` da entrada); `get_opensearch_connection` retorna o client embrulhado em `ClienteProjeto` |
| `dashboards/opensearch/cliente_projeto.py` (novo) | `ClienteProjeto(client, projeto_id)`: injeta o filtro em `search`/`msearch`/`count` e recusa escritas |
| `dashboards/opensearch_query.py` | Com projeto, `options` sai da agregação já filtrada (só o projeto), no dashboard e em `get_alerts` |
| `dashboards/decorators.py` (novo) | `login_or_projeto_required` (trata `?hash=` na entrada) e `bloqueado_no_projeto` |
| `dashboards/views.py` | Decorators; `aplica_filtro_projeto` em `dashboards`, `list_results_view` e `alerts_view`; qualquer POST no dataset com projeto → 403 (inclui `export`); checagem de dono em `record_view` e `visualization` |
| `dashboards/context_processors.py` (novo) | Expõe `projeto_acesso` aos templates |
| `dashboards/templates/dashboards.html` | Com `projeto_acesso`: título do projeto, sem o seletor de assunto, sem "Limpar" e sem feedback de IA |
| `dashboards/templates/dataset.html` | Com `projeto_acesso`: sem checkboxes/ações e sem o botão "Baixar csv" |
| `tema_*/templates/base_navbar.html` | Conferir que "Menu", "Alterar senha" e "Logout" já dependem de `user.is_authenticated` |
| `configs/local.py` | `PROJETO_HASH_KEY` |

Não há migração no Gestão nem rota nova: a entrada é o próprio `/dashboard`.

### Entrada e sessão
```python
# dashboards/decorators.py
def login_or_projeto_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        token = request.GET.get('hash')
        if token and getattr(settings, 'PROJETO_HASH_KEY', ''):
            ds = request.GET.get('ds', '')
            projeto_id = valida_hash(token, ds)
            if projeto_id is None:
                raise PermissionDenied('Link inválido')                  # req. 4.3
            if not DataSource.objects.filter(slug=ds).exists():
                raise Http404('Dataset inexistente neste ambiente')     # req. 4.4
            set_projeto_acesso(request, projeto_id, ds)                 # projeto_acesso + opensearch_index
            return redirect(request.path)                               # tira hash/ds da URL
        if get_projeto_acesso(request) or request.user.is_authenticated:
            return view(request, *args, **kwargs)
        return redirect_to_login(request.get_full_path())
    return wrapper
```

```python
# dashboards/opensearch/session.py
def set_opensearch_index(request, index):
    if get_projeto_acesso(request) and not request.user.is_authenticated:
        return                                                  # ds fixo do link (req. 5.2)
    if not DataSource.objects.filter(slug=index, grupos__in=request.user.groups.all()).exists():
        raise PermissionDenied("Índice inválido")
    limpa_projeto_acesso(request)                               # req. 9.2
    request.session['opensearch_index'] = index
```

`set_projeto_acesso` grava `projeto_acesso` e também `projeto_ds`, que é o `ds` da entrada. `_get_opensearch_connection` só dispensa o grupo quando `opensearch_index == projeto_ds`. Como as views seguintes não dependem de parâmetro, paginação e filtros mantêm o acesso, e os links e o JavaScript atuais não mudam.

O redirecionamento usa `request.path` (`/dashboard`). O `?ds=` normal das views não é afetado, porque só é tratado quando não há `hash`.

### Filtro forçado — duas camadas
**1. No cliente (garantia).** Nem todos os construtores de `opensearch_query.py` aplicam `monitoramento_id`: `_list_termos_search_query` e `_count_terms_search` filtram só por `busca_id`, e `_filter_options` tem o filtro comentado. Sem um ponto único, um `busca_id` de outro projeto vazaria contagens e termos, e os nomes de todos os projetos chegariam ao `queryOptions` do JavaScript. Por isso, no modo projeto, `get_opensearch_connection` devolve um invólucro:

```python
class ClienteProjeto:
    """Client OpenSearch que só enxerga um projeto e não escreve."""

    def __init__(self, client, projeto_id):
        self._client = client
        self._termo = {'term': {'monitoramento_id': projeto_id}}

    def _restringe(self, body):
        body = dict(body or {})
        original = body.get('query', {'match_all': {}})
        body['query'] = {'bool': {'filter': [self._termo], 'must': [original]}}
        return body

    def search(self, body=None, **kwargs):
        return self._client.search(body=self._restringe(body), **kwargs)

    def count(self, body=None, **kwargs):
        return self._client.count(body=self._restringe(body), **kwargs)

    def msearch(self, body, **kwargs):
        # body alterna cabeçalho / consulta; só as consultas (posições ímpares) são restringidas
        ...

    def __getattr__(self, nome):
        raise PermissionDenied(f'Operação {nome} indisponível no acesso por projeto')
```

Envolver a consulta original num `bool.must` (em vez de alterar o `bool` existente) funciona para qualquer formato de consulta. `update`, `index` e `delete` caem no `__getattr__` e são recusados. O invólucro SHALL aceitar `body` posicional (ex.: `views.py:676`).

**2. Nos filtros (coerência da tela).**
```python
def aplica_filtro_projeto(request, filters):
    projeto_id = get_projeto_acesso(request)
    if projeto_id:
        filters['monitoramento_id'] = projeto_id
    return filters
```
É chamado logo depois de montar `filters` em `dashboards`, `list_results_view` e `alerts_view`, sobrescrevendo qualquer valor vindo do GET. A consulta de `options`, já filtrada pelo invólucro, devolve só o próprio projeto. Dela sai também o `monitoramento_nome` usado como título (req. 6.8).

### Exportação bloqueada
O link serve só para visualizar (req. 8). No modo projeto:
- `dataset.html` não renderiza o formulário do botão "Baixar csv";
- `list_results_view` responde 403 a qualquer POST, inclusive `action=export`, antes de chegar a `dataset_export_csv`. O Mage nunca é chamado.

`dataset_export_csv` fica como antes, só para usuários logados (`request.user.email`). Como o Mage consulta o OpenSearch por conta própria, fora do `ClienteProjeto`, bloquear é mais seguro do que tentar filtrar a exportação.

### Permissões por view
| View | Decorator | Observação |
|---|---|---|
| `dashboards` | `login_or_projeto_required` | Única view que aceita `?hash=` (entrada) |
| `list_results_view`, `alerts_view` | `login_or_projeto_required` | Qualquer POST com projeto → 403: arquivar, tag e `export` (req. 7.5, 8) |
| `visualization`, `record_view` | `login_or_projeto_required` | `get_record` + checa `_source.monitoramento_id == projeto_id`, senão 404 |
| `busca_id_by_monitoramento` | `login_or_projeto_required` | Com projeto, só aceita `id == projeto_id` |
| `generate_interpretation_ia` | `login_or_projeto_required` | Recebe os dados do gráfico já filtrados pela página |
| `salvar_feedback`, `log_query_by_id`, `tag_*`, `migrate_posts`, deploy, debug | `bloqueado_no_projeto` (somado ao decorator atual) | 403 |
| `menu`, pastas do GED | `bloqueado_no_projeto` | Redireciona para o dashboard |
| `/admin/` | inalterado | Exige login de staff; o link não dá acesso |

Só `dashboards` trata `?hash=`. Nas outras views, `login_or_projeto_required` ignora o parâmetro e usa apenas a sessão.

### Decisões
- **O `ds` entra no HMAC.** Isso fixa o dataset no link e dispensa um cadastro extra no Gestão para dizer quais datasets aceitam projetos do Capitu. O formato visível continua `{id}-{hash}`.
- **A entrada é pelo próprio `/dashboard`**, como o `?ds=` atual, e redireciona para tirar o `hash` da URL.
- **Sem API entre os sistemas.** O token traz o `projeto.id`, que é o `monitoramento_id`. O nome vem de `monitoramento_nome` nos documentos.
- **O prefixo é gravado na criação, e não na edição.** Um prefixo ajustado depois no admin não é sobrescrito ao editar o projeto pela tela do usuário.
- **A sessão anônima** do Django guarda o acesso. Não é criado usuário. `request.user` continua `AnonymousUser`. Por isso `list_results_view` precisa tratar `can_archive_record` sem `request.user.groups` (fica `False`).

## Testes

### Capitu
- `token_projeto(7, 'vtrack-telegram')` tem o formato `7-<32 hex>` e é estável. Com outro `ds` ou outra chave, o hash muda.
- `url_resultado` = `{GESTAO_URL}/dashboard?hash=7-…&ds=vtrack-telegram`. É `None` sem `GESTAO_URL`, sem `PROJETO_HASH_KEY` ou com `prefix` vazio.
- `telegram_project` (POST válido) cria o projeto com `prefix='vtrack-telegram'`. `editar_projeto` não altera o prefixo, nem um prefixo trocado no admin.
- Painel: a coluna "Resultado" aparece com a configuração completa. Projeto Telegram criado pelo formulário → link com `target="_blank"`. Projeto Twitter sem prefixo → "—". Projeto Twitter com prefixo preenchido no admin → link com o `ds` desse prefixo. Sem configuração, a coluna não aparece.

### Gestão (`dashboards/tests.py`, OpenSearch mockado)
- `GET /dashboard?hash=<válido>&ds=vtrack-telegram` anônimo → 302 para `/dashboard`, sessão com `projeto_acesso = 7` e `opensearch_index = 'vtrack-telegram'`, sem checar grupo.
- Hash alterado, id trocado, `ds` trocado (`ds=gestao` com o hash de `vtrack-telegram`) ou `ds` ausente → 403, sessão inalterada.
- Hash válido para um `ds` sem `DataSource` no ambiente → 404.
- Sem `PROJETO_HASH_KEY` → o `hash` é ignorado e o anônimo vai para o login.
- **Persistência:** depois da entrada, `GET /dataset?page=2`, `GET /dataset?rede=x`, `GET /alerts` e `GET /visualization/<id>` (sem `hash`, `ds` ou `monitoramento_id`) funcionam como anônimo e consultam o índice `vtrack-telegram` com `monitoramento_id = 7`.
- `GET /dashboard?ds=gestao` (sem `hash`) no modo projeto → ignorado, continua `vtrack-telegram`.
- Dashboard com `?monitoramento_id=99` → a consulta tem `monitoramento_id = 7`.
- **Todo** corpo enviado ao client mockado (`search`, `count` e cada consulta do `msearch`) no dashboard, no dataset e em alertas contém `{'term': {'monitoramento_id': 7}}`, inclusive com `busca_id` de outro projeto.
- O HTML do dashboard e o de alertas não contêm nome nem id de outro projeto.
- `record_detail` e `visualization` de registro com `monitoramento_id = 99` → 404. Do próprio projeto → 200.
- Dataset no modo projeto sem o botão "Baixar csv". POST `action=export` → 403 e Mage não chamado. Usuário logado continua vendo o botão e exportando para o próprio e-mail.
- POST no dataset (arquivar e tag) → 403. `ClienteProjeto.update(...)` → `PermissionDenied`.
- Feedback de IA, tags e `log_query` → 403. Menu → redireciona para o dashboard. `/admin/` → login.
- Usuário logado com `?ds=` válido (sem `hash`) → `projeto_acesso` removido da sessão.
- Sem `hash` e sem `projeto_acesso`, os testes atuais continuam passando (inclusive o padrão `'gestao'`).
