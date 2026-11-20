# Design — Ajustes da issue #40 (menu, link do canal e índice do projeto no "Resultado")

## Visão geral
Três correções independentes. As duas primeiras são só no Capitu (templates, CSS, uma rota nomeada). A terceira altera os dois sistemas: o Capitu passa o índice do projeto no link, e o Gestão usa esse índice no acesso por projeto.

| Item | Repositório | Natureza |
|---|---|---|
| 1. Menu | `twitsearch` | `name=` na rota e `href` absolutos em `base.html`; CSS de rolagem |
| 2. Link do canal | `twitsearch` | Templates `lista_canais.html` e `canal_mensagens.html`; CSS `#telegram-canais` |
| 3. Índice no "Resultado" | `twitsearch` e `gestao-minerva` | Hash e link no Capitu; entrada, sessão e índice no Gestão |

## 1. Menu superior

### Componentes
| Arquivo | Alteração |
|---|---|
| `core/urls.py` | `re_path(r'^$', index, name='index')` |
| `templates/base.html` | `navbar-brand` e "Início" → `{% url 'index' %}`; demais itens → `{% url 'index' %}#como-funciona`, `#acesso`, `#institucional` |
| `core/static/css/style.css` | `scroll-margin-top` nos alvos das âncoras, se a verificação mostrar o título coberto pelo cabeçalho |

### Decisões
- **URL absoluta com fragmento, sem JS.** Na página inicial, `/#como-funciona` é a mesma página e o navegador só rola. Fora dela, carrega `/` e posiciona na seção. Não é preciso detectar a página atual no template.
- **`#main` deixa de ser usado no menu.** "Início" aponta para `/`. O `id="main"` do `<main>` continua no `base.html` (não é removido).
- **Cabeçalho fixo.** O `header` é `sticky-top` e o `style.css` não define `scroll-margin`. Os alvos são `<span id="…">` vazios dentro de `home.html`. Se a verificação (tarefa 4) mostrar o título da seção sob o cabeçalho, aplicar `scroll-margin-top` igual à altura do cabeçalho (medir em 1280px e 390px) num seletor escopado aos três `id`s. Não criar regra global de `:target`.
- **Celular.** O `navbar-collapse` continua aberto depois do clique quando o link é da mesma página. Isso já acontece hoje e não faz parte do pedido; registrar se incomodar na verificação.

## 2. Link do canal

### Componentes
| Arquivo | Alteração |
|---|---|
| `templates/lista_canais.html` | Coluna Canal: `<a class="tc-canal-msgs">` envolvendo `@usuario` + `titulo`, para `canal_mensagens`; `<a class="tc-tg">` só com o ícone, para `t.me` |
| `templates/canal_mensagens.html` | Ícone do `tc-canal-link` (cabeçalho) e do `tc-m-link` (mensagens) trocado pelo logo do Telegram |
| `templates/_icone_telegram.html` (novo) | SVG inline do logo, incluído com `{% include %}` nos três pontos |
| `core/static/css/style.css` | Estilos de `.tc-canal-msgs` e `.tc-tg` em `#telegram-canais` (desktop e `max-width: 767.98px`) |
| `telegram/tests.py` | Ajuste das asserções sobre os links da coluna Canal |

### Marcação da coluna Canal
```html
<td class="col-canal">
  <div class="tc-canal-linha">
    <a class="tc-canal-msgs" href="{% url 'canal_mensagens' c.pk %}{% if voltar_qs %}?{{ voltar_qs }}{% endif %}">
      <span class="tc-canal-user">@{{ c.username }}</span>
      {% if c.titulo %}<span class="tc-canal-titulo">{{ c.titulo }}</span>{% endif %}
    </a>
    <a class="tc-tg" href="https://t.me/{{ c.username }}" target="_blank" rel="noopener"
       aria-label="Abrir @{{ c.username }} no Telegram (nova aba)" title="Abrir no Telegram">
      {% include "_icone_telegram.html" %}
    </a>
  </div>
  {% if c.status != "A" %}<span class="tc-status">{{ c.get_status_display }}</span>{% endif %}
</td>
```
- **Um link para `@usuario` + título.** O texto acessível do link é "@usuario Título", sem `aria-label` próprio. O `voltar_qs` é o mesmo já usado no link do número de mensagens.
- **Dois links irmãos, nunca aninhados.** `<a>` dentro de `<a>` é HTML inválido; por isso o ícone fica ao lado, no mesmo `div` flex.
- **Tipografia sem mudança.** `@usuario` (14px / 600 / `#1E1D30`; celular 15px) e título (13px / 400 / `#6B6C72`; celular 12px) mantêm os valores do req. 11.5 de `telegram-lista-canais`. O hover do link só sublinha o `@usuario` e muda sua cor para `#0066FF`, para indicar que é clicável.
- **`.tc-canal-titulo` passa de `div` para `span` com `display: block`**, porque fica dentro de um `<a>` (inline).

### Ícone do Telegram
- SVG inline (avião de papel dentro do círculo), `viewBox="0 0 24 24"`, `fill="currentColor"`, `aria-hidden="true"`, `focusable="false"`. Sem biblioteca de ícones: o `base.html` carrega só o Bootstrap.
- O include recebe o tamanho por variável (`{% include "_icone_telegram.html" with tam=16 %}`): 16px no grid, 13px no cabeçalho do canal (tamanho do ícone atual) e o tamanho atual do `tc-m-link` nas mensagens.
- **Cor.** `currentColor` com `color: #0066FF` (hover `#0052CC`), a cor de link do sistema. O azul oficial do Telegram (`#229ED9`) não é usado, para não introduzir uma cor fora da paleta do protótipo.
- **Alvo de toque.** `.tc-tg` é `inline-flex`, centralizado, com 32px × 32px no desktop e 44px × 44px no celular, raio 50%, fundo transparente (`#EEF4FF` no hover e no foco). Foco visível com o mesmo `outline` dos outros links do bloco.

### Página do canal
- Cabeçalho: o `tc-canal-link` (`@usuario` → `t.me`) continua igual; só o `<svg>` interno muda.
- Mensagens: o `tc-m-link` continua com `aria-label="Abrir no Telegram"`; só o `<svg>` interno muda.

### Protótipo
Atualizar no protótipo do Claude Design (https://claude.ai/artifact/MFVvasjD7cU8ZZ8gdurZ4r) as telas `Main`, `ListaMobile`, `Canal` e `CanalMobile` com o novo ícone e o link no título, como foi feito no req. 11.13 de `telegram-lista-canais`. O protótipo continua sendo a referência visual.

## 3. Índice do projeto no "Resultado"

### Como funciona hoje
```
Capitu                                   Gestão
url_resultado                            dashboard?hash&ds   (decorators.login_or_projeto_required)
  hash = HMAC("projeto:{id}:telegram")     valida_hash(token, ds)
  ?hash=…&ds=telegram           ───────►   set_projeto_acesso(id, ds) → sessão
                                           get_opensearch_connection
                                             conexão = DataSource[ds].conexao
                                             índice  = conexao['index']   (ex.: telegram*)
                                             client  = ClienteProjeto(filtra monitoramento_id)
```
O consumidor grava em `{prefix}-{ano}-{mês}-1`. Com `prefix = capitu`, os documentos vão para `capitu-*`, fora de `telegram*`.

### Solução: `idx` no link, assinado pelo hash
```
Capitu                                    Gestão
  hash = HMAC("projeto:{id}:telegram:capitu")
  ?hash=…&ds=telegram&idx=capitu  ───────►  valida_hash(token, ds, idx)
                                            set_projeto_acesso(id, ds, idx)
                                            get_opensearch_connection
                                              conexão = DataSource[ds].conexao   (igual)
                                              índice  = "capitu-*"               (só no acesso por projeto)
```
- O **`DataSource` continua sendo a fonte da conexão** (host, porta, credenciais) e da existência do dataset no ambiente. Só o nome do índice muda, e só no acesso por projeto.
- Todas as views do Gestão obtêm o índice por `get_opensearch_connection(request)` (9 chamadas em `dashboards/views.py`; nenhuma lê `DataSource.conexao['index']` diretamente). A troca do índice acontece num ponto só.
- O hash cobre o `idx`. Sem isso, quem tem o link poderia trocar o índice e ler o mesmo `monitoramento_id` em um índice de outra origem, onde o id pode significar outra coisa (mesmo motivo de o `ds` entrar no hash, req. 1.2 de `projeto-resultado-gestao`).

### Componentes — Capitu (`twitsearch`)
| Arquivo | Alteração |
|---|---|
| `core/hash_projeto.py` | `hash_projeto(projeto_id, ds, indice='')` e `token_projeto(projeto_id, ds, indice='')`. Mensagem `projeto:{id}:{ds}` sem índice e `projeto:{id}:{ds}:{indice}` com índice |
| `core/models.py` (`Projeto.url_resultado`) | Com `prefix`: `params = {'hash': token_projeto(pk, DS_TELEGRAM, prefix), 'ds': DS_TELEGRAM, 'idx': prefix}`. Sem `prefix`: igual a hoje |
| `telegram/models.py` | Atualizar o comentário de `DS_TELEGRAM`: o `ds` escolhe o `DataSource`; o índice vem de `Projeto.prefix` |
| `telegram/models.py`, `telegram/views.py` (`telegram_project`) | Constante `PREFIXO_TELEGRAM = 'telegram'`, gravada em `Projeto.prefix` na criação (req. 3.6). Separada de `DS_TELEGRAM`: uma é o prefixo do índice, a outra o slug do `DataSource`, e só coincidem no valor |
| `core/tests.py`, `telegram/tests.py` | Substituir `test_prefixo_nao_altera_o_link` e as asserções de "o prefixo não interfere" por testes do `idx` |
| `.kiro/specs/projeto-resultado-gestao/requirements.md` | Nota nos req. 1.1 e 3.2 apontando para esta spec |

- **Regra de índice nos dois lados.** O `clean_prefix` do admin aceita prefixo começando por `-`, e projetos antigos podem ter prefixo gravado antes dele (com maiúsculas ou `*`). Por isso `url_resultado` só envia `idx` quando o prefixo casa com `^[a-z][a-z0-9-]{0,19}$`, a mesma expressão que o Gestão valida (constante `REGEX_INDICE` em `core/hash_projeto.py`). Fora dela, o link é o de hoje. Assim, o Capitu nunca gera um link que o Gestão recusaria.
- `url_resultado` não acrescenta `-*` nem curinga: o Capitu manda o prefixo, e o Gestão monta o padrão. Assim, a regra de nome de índice fica num lugar só, perto de quem consulta.

### Componentes — Gestão (`gestao-minerva`)
| Arquivo | Alteração |
|---|---|
| `utils/hash_projeto.py` | `hash_projeto(projeto_id, ds, indice='')` e `valida_hash(token, ds, indice='')`, com a mesma fórmula do Capitu |
| `dashboards/decorators.py` (`login_or_projeto_required`, `entrada=True`) | Lê `idx = request.GET.get('idx', '')`; valida com `^[a-z][a-z0-9-]{0,19}$` (vazio é aceito); `valida_hash(token, ds, idx)`; `set_projeto_acesso(request, projeto_id, ds, idx)` |
| `dashboards/opensearch/session.py` | `set_projeto_acesso(request, projeto_id, ds, indice='')` grava `projeto_indice` (ou remove a chave, se vazio); `limpa_projeto_acesso` remove `projeto_indice`; nova `get_projeto_indice(request)` |
| `dashboards/opensearch/datasource.py` (`get_opensearch_connection`) | No acesso por projeto com `projeto_indice`: retorna `f'{indice}-*'` no lugar de `connection_dict['index']` |
| `dashboards/tests.py` | Casos novos (ver "Testes") |

Esboço de `get_opensearch_connection`:
```python
def get_opensearch_connection(request):
    index = get_opensearch_index(request)
    connection_dict = _get_opensearch_connection(request, index)
    client = connect_opensearch(connection_dict)
    index_name = connection_dict['index']

    projeto_id = get_projeto_acesso(request)
    if projeto_id:
        client = ClienteProjeto(client, projeto_id)
        indice = get_projeto_indice(request)
        if indice:
            index_name = f'{indice}-*'   # mesmo padrão de nome do vtrack-consumidor

    return client, index_name
```

### Decisões
- **`ds` continua `telegram`.** Ele seleciona o `DataSource` que tem a conexão com o cluster onde estão os índices `vtrack`/Capitu. Passar o prefixo no lugar do `ds` (alternativa B) exigiria um `DataSource` por prefixo.
- **Padrão `{idx}-*`, e não `{idx}*`.** O consumidor do Telegram grava em `{prefix}-{ano}-{mês}-1`. Com `-*`, o prefixo `capitu` não alcança índices como `capitulo-…` ou `capitu2-…`.
- **Só o índice do projeto.** O resultado mostra o que está em `{idx}-*`. Os documentos gravados antes da troca do prefixo não aparecem (Pendência 1 dos requisitos).
- **Compatibilidade.** Sem `idx`, a fórmula do hash e o comportamento são os de hoje: links já enviados continuam valendo, e projetos sem prefixo não mudam.
- **Sem mudança no fluxo logado.** `set_opensearch_index` só ganha a limpeza de `projeto_indice` (via `limpa_projeto_acesso`, que ele já chama). Checagem de grupo e índice do `DataSource` continuam iguais.
- **Ordem de deploy.** Publicar o Gestão antes do Capitu. Com o Capitu primeiro, os links com `idx` dariam 403 no Gestão antigo, porque ele calcularia o hash sem o índice.

### Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| **B.** `ds = prefix` (um `DataSource` por prefixo, sem código no Gestão) | Exige cadastrar um `DataSource` com grupos e conexão a cada prefixo novo, com slug igual ao prefixo. Sem o cadastro, o link dá 404. O acoplamento prefixo = slug não existe hoje (ex.: slug `vtrack-telegram`, índice `vtrack-telegram-test*`) |
| **C.** Campo novo "Dataset do Gestão" no `Projeto` | Migração e mais um campo manual no admin, além do `prefix`, para a mesma informação |
| **D.** Consultar `{idx}-*` e o índice do `DataSource` ao mesmo tempo | Mostra o histórico de antes da troca, mas mistura índices sem o admin pedir. Fica como opção da Pendência 1 |

### Riscos e cuidados
- **Regressão em outros projetos com prefixo.** A mudança vale para todo projeto Telegram com prefixo válido. Um projeto que hoje aparece pelo índice do `DataSource` e tem documentos em índice sem o sufixo `-{ano}-{mês}-1` (execuções antigas do consumidor, outro exportador, `fixed_index` de depuração) deixaria de aparecer. A tarefa 1 lista esses projetos e confere onde estão os documentos antes do deploy.
- **Slug do `DataSource`.** O link usa `ds=telegram`, mas o script `docs/scripts/cadastrar_ds_telegram.py` do Gestão cadastra o slug `vtrack-telegram`. A tarefa 1 confirma qual slug existe no ambiente apontado por `GESTAO_URL`; se não for `telegram`, ajustar `DS_TELEGRAM` (problema que já existe hoje, independente desta entrega).
- **Mesmo cluster.** Se o índice do projeto estiver em outro OpenSearch, a conexão do `DataSource` `telegram` não o alcança, e o dashboard fica vazio. A tarefa 1 confirma isso em produção.
- **Padrão sem índices.** Se `capitu-*` não existir ainda, a consulta com curinga devolve zero documentos (o `allow_no_indices` padrão é `true`). O dashboard fica vazio, sem erro, como o req. 4.6 de `projeto-resultado-gestao`.
- **`msearch`.** O `ClienteProjeto` restringe só as consultas. Os cabeçalhos precisam usar o `index_name` devolvido por `get_opensearch_connection` para herdar o índice do projeto. Isso ainda não foi conferido nas views que montam `msearch`; a tarefa 13 confere, e o teste cobre.
- **Chave nos dois lados.** A fórmula nova tem de ser idêntica em `core/hash_projeto.py` e `utils/hash_projeto.py`. Um teste em cada repositório fixa o hash esperado para um par conhecido (`projeto 100`, `telegram`, `capitu`).

## Testes

### Capitu (`telegram/tests.py`, `core/tests.py`)
- Menu: `/painel/` e `/telegram/listas/` renderizam `href="/#como-funciona"`, `href="/#acesso"`, `href="/#institucional"`, e "Início" e logo com `href="/"`; nenhum `href="#…"` no `nav`.
- Grid: o link que contém `@usuario` aponta para `canal_mensagens` com o `voltar` da seleção; o `titulo` está dentro do mesmo link; existe um link para `https://t.me/<usuario>` com `target="_blank"`, `rel="noopener"` e `aria-label="Abrir @<usuario> no Telegram (nova aba)"`; nenhum link de `t.me` contém o texto `@usuario`.
- Página do canal: `@usuario` continua apontando para `t.me`; o logo do Telegram está no cabeçalho e em cada mensagem.
- `hash_projeto(100, 'telegram')` igual ao valor de hoje (compatibilidade); `hash_projeto(100, 'telegram', 'capitu')` igual ao valor fixado no teste do Gestão.
- `url_resultado` com `prefix='capitu'`: contém `ds=telegram`, `idx=capitu` e o token com índice. Sem `prefix`: igual ao link de hoje, sem `idx`. Trocar o prefixo muda o link.
- Edição e criação continuam sem gravar `prefix` (testes existentes).

### Gestão (`dashboards/tests.py`)
- Link com `idx` válido → 302 para `/dashboard`, sessão com `projeto_indice`.
- `idx` trocado, removido ou acrescentado a um link sem `idx` → 403, sessão intacta.
- `idx` fora da regra (`Capitu`, `1abc`, `a*`, `a,b`, 21 caracteres) → 403.
- Com `projeto_indice`, `get_opensearch_connection` devolve `capitu-*` e a conexão do `DataSource` `telegram`. Sem `projeto_indice`, devolve `conexao['index']`.
- Link sem `idx` → comportamento de hoje (testes existentes continuam passando).
- Novo link substitui o índice anterior; `set_opensearch_index` de usuário logado remove `projeto_indice`.
- `msearch` no acesso por projeto usa o índice do projeto nos cabeçalhos e o filtro por `monitoramento_id` nas consultas.
