# Design — Adicionar lista de canais (com descrição)

## Mockups
Canvas **"Capitu — Listas de Canais Telegram"**: https://claude.ai/artifact/MFVvasjD7cU8ZZ8gdurZ4r

Os mockups estão na página **"Issue #46 — Adicionar lista"**, ao lado das telas que já existiam. A página 1 não foi alterada e continua sendo o "como está".

| Artboard | O que mostra |
|---|---|
| `46-AdicionarLista.dc.html` | Tela `/telegram/listas/adicionar/`. Tweak "estado": *Vazio*, *Sem arquivo*, *Com arquivo*, *Nome repetido* |
| `46-Listas.dc.html` | Tela `/telegram/listas/` com o botão "Adicionar lista", e a dica com a descrição sobre a tag. Tweak "cenario": *Duas listas selecionadas*, *Logo após criar lista vazia* (mensagem de sucesso + estado vazio com o texto novo), *Nenhuma selecionada*. Tweak "dicaAberta" fixa a dica de uma tag, para ela aparecer no canvas sem hover |
| `46-ListasMobile.dc.html` | Mesma tela a 390 px, com o botão "Adicionar lista" em largura total. Sem dica, porque não há hover |

## Fluxo
```
/telegram/listas/ ──"Adicionar lista"──▶ /telegram/listas/adicionar/?origem=listas
                                           │ POST sem arquivo → Lista vazia
                                           │ POST com arquivo → importa_lista(...)
                                           ▼
                                         302 → /telegram/listas/?lista=<nova>

/telegram/projetos/novo/ ──"Adicionar lista"──▶ /telegram/listas/adicionar/
                                                  └─▶ 302 → /telegram/projetos/novo/?lista=<nova>
/telegram/projetos/<id>/editar/ ──▶ /telegram/listas/adicionar/?projeto=<id>
                                     └─▶ 302 → /telegram/projetos/<id>/editar/?lista=<nova>

/telegram/listas/importar/          ──301──▶ /telegram/listas/adicionar/  (query string preservada)
/telegram_project/importar_lista/   ──301──▶ /telegram/listas/adicionar/
```

## Arquivos

| Arquivo | Alteração |
|---|---|
| `telegram/models.py` | `Lista.descricao = models.TextField('Descrição', blank=True)` |
| `telegram/migrations/0007_lista_descricao.py` (novo) | `AddField`, gerada com `makemigrations telegram` |
| `telegram/admin.py` | `ListaAdmin.fields = ('nome', 'publica', 'descricao')` |
| `telegram/forms.py` | `ImportListaForm` → `AdicionarListaForm`, com o campo `descricao` e `arquivo` opcional |
| `telegram/importacao.py` | `importa_lista(..., descricao='')` grava a descrição |
| `telegram/views.py` | `importar_lista` → `adicionar_lista`, com a regra de origem e o caminho sem arquivo. `lista_canais` passa `descricao` nos itens e `adicionar_url` no contexto (no lugar de `importar_url`) |
| `core/urls.py` | Rota nova `telegram/listas/adicionar/` (`adicionar_lista`). `telegram/listas/importar/` vira `RedirectView`, e o redirect antigo `telegram_project/importar_lista/` passa a apontar para `adicionar_lista` |
| `templates/importar_lista.html` → `templates/adicionar_lista.html` | Renomeado (`git mv`). Título, campo descrição, botão "Adicionar lista" |
| `templates/lista_canais.html` | Botão "Adicionar lista", textos dos estados vazios, dica nas tags, item novo na legenda |
| `templates/telegram_project.html` | Botão "Adicionar lista" (rótulo, ícone, `title`, `{% url 'adicionar_lista' %}`) |
| `core/static/css/style.css` | Estilos `.tc-tag-item`, `.tc-dica` e `.tc-legenda-dica`. É a fonte versionada. `static/` é o `STATIC_ROOT`, gerado pelo `collectstatic`, e não é editado |
| `core/static/js/lista_canais.js` (novo) | Só a tecla Esc para esconder a dica (~15 linhas) |
| `telegram/tests.py` | Ajuste dos testes existentes e testes novos (ver `tasks.md`) |

## Modelo
```python
class Lista(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField('Descrição', blank=True)
    dono = models.ForeignKey(User, on_delete=models.PROTECT)
    publica = models.BooleanField('Qualquer usuário pode utilizá-la', default=False)
    canais = models.ManyToManyField(Canal, blank=True)
```

## Formulário
```python
class AdicionarListaForm(forms.Form):
    nome = forms.CharField(label='Nome da lista', max_length=100)
    descricao = forms.CharField(
        label='Descrição (opcional)', required=False, strip=True,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Aparece como dica sobre a lista na tela de Listas de Canais.')
    publica = ...  # igual a hoje
    arquivo = forms.FileField(
        label='Arquivo de canais (opcional)', required=False,
        widget=forms.ClearableFileInput(attrs={'accept': '.csv,.xlsx'}),
        help_text='CSV ou Excel com uma única coluna: a URL (https://t.me/canal) ou o identificador '
                  '(@canal) de cada canal. Sem arquivo, a lista é criada vazia.')

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get('arquivo')
        if arquivo and not arquivo.name.lower().endswith(('.csv', '.xlsx')):
            raise forms.ValidationError('Envie um arquivo .csv ou .xlsx.')
        return arquivo
```
`clean_nome` e o `__init__` (classes CSS) continuam iguais.

## View
```python
ORIGENS = {'listas': ('lista_canais', 'Listas de Canais')}

@login_required
def adicionar_lista(request):
    projeto = projeto_editavel(request.user, request.GET.get('projeto'))
    if projeto:
        voltar_url, voltar_rotulo = reverse('editar_projeto', args=[projeto.pk]), 'Editar projeto'
    else:
        rota, voltar_rotulo = ORIGENS.get(request.GET.get('origem'), ('telegram_project', 'Nova coleta Telegram'))
        voltar_url = reverse(rota)
    if request.method == 'POST':
        form = AdicionarListaForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            dados = form.cleaned_data
            if not dados['arquivo']:
                lista = Lista.objects.create(nome=dados['nome'], descricao=dados['descricao'],
                                             dono=request.user, publica=dados['publica'])
                messages.success(request, f'Lista "{lista.nome}" criada, ainda sem canais.')
                return redirect(f'{voltar_url}?lista={lista.pk}')
            try:
                ...  # bloco atual: le_primeira_coluna, MAX_LINHAS, importa_lista(..., descricao=dados['descricao'])
            except ...:  # tratamento de erro atual, sem mudanças
            else:
                ...  # mensagem atual
                return redirect(f'{voltar_url}?lista={resultado["lista"].pk}')
    else:
        form = AdicionarListaForm(user=request.user)
    return render(request, 'adicionar_lista.html',
                  {'form': form, 'voltar_url': voltar_url, 'voltar_rotulo': voltar_rotulo})
```
- `?projeto=` tem prioridade sobre `?origem=`. Um `origem` desconhecido cai no padrão `telegram_project`.
- O `?origem=listas` precisa sobreviver ao POST. Como o `<form>` não tem `action`, ele envia para a URL atual com a query string, e isso já basta. O mesmo vale hoje para `?projeto=`.
- `/telegram/listas/?lista=<pk>` já seleciona a lista: `lista_canais` lê `request.GET.getlist('lista')`.

## Tela de listas — dica com a descrição
O contexto ganha `descricao` em cada item:
```python
itens = [{..., 'descricao': lista.descricao.strip()} for lista in listas]
```
Template (cada tag fica num invólucro, e a dica é irmã do link, não filha):
```django
<span class="tc-tag-item">
  <a href="{{ l.url }}" class="tc-tag ..." aria-pressed="..."
     {% if l.descricao %}aria-describedby="dica-lista-{{ l.id }}"{% endif %}>…</a>
  {% if l.descricao %}
    <span class="tc-dica" role="tooltip" id="dica-lista-{{ l.id }}">{{ l.descricao }}</span>
  {% endif %}
</span>
```
- A dica fica **fora** do `<a>` para não entrar no nome acessível do link. Ela só é anunciada como descrição, via `aria-describedby`.
- CSS:
  - `.tc-tag-item { position: relative; display: inline-flex }`
  - `.tc-dica` é absoluta, acima da tag (`bottom: calc(100% + 8px)`), alinhada à esquerda, com `max-width: 320px` e `width: max-content`.
  - Fundo `#1E1D30`, texto branco 13px/1.5, `border-radius: 10px`, seta de 6px.
  - `white-space: pre-line` e `-webkit-line-clamp: 4`.
  - Escondida com `opacity: 0; visibility: hidden`. Aparece em `.tc-tag-item:hover` e `.tc-tag-item:focus-within`, com transição de 120 ms, desligada em `prefers-reduced-motion`.
  - Fica escondida em `@media (hover: none)`, junto com o item da legenda que fala em passar o mouse.
- `lista_canais.js`: Esc numa tag focada adiciona `.dica-oculta` ao `.tc-tag-item`, e o `blur` remove a classe.
- A descrição só aparece na dica, sem nenhum bloco extra na tela (req. 5.6).

## Tela de listas — ordenação, densidade e "Limpar seleção" (req. 7)
- Ordenação: em `lista_canais`, `order_by('-num_participantes', 'username')` vira `order_by('-num_mensagens', '-num_participantes', 'username')`.
- Densidade, em `core/static/css/style.css`:
  - `.tc-grid td` passa a ter `padding: 8px 16px`;
  - `.tc-grid th` passa a ter `padding: 10px 16px`;
  - `.col-desc span` passa a ter `line-height: 1.4`;
  - `.tc-canal-titulo` perde o `margin-top`.
  O bloco `@media (max-width: 767.98px)`, dos cartões, fica como está.
- "Limpar seleção":
  - sai o `<div class="tc-listas-topo">` (rótulo "Listas" + link);
  - o link vai para o fim da `.tc-legenda`, com `margin-left: auto`;
  - o rótulo some; o `role="group" aria-label="Listas de canais"` das tags continua;
  - `.tc-legenda` passa a ter `align-items: center`, e o `aria-hidden="true"` sai da legenda e fica só nos itens de legenda, para o link continuar acessível;
  - a regra `.tc-listas-topo` do CSS (inclusive a versão mobile, linha ~1756) é removida.

## Textos

| Lugar | Antes | Depois |
|---|---|---|
| Botão no cabeçalho de `/telegram/listas/` | Importar lista (ícone de upload) | Adicionar lista (ícone +) |
| Estado "sem listas" | Importar uma lista | Adicionar uma lista |
| Estado "lista sem canais" | Adicione canais à lista pelo admin ou importe um arquivo. | As listas selecionadas ainda não têm canais. Fale com o administrador para incluí-los. |
| Botão no formulário de projeto | Importar lista (`title` "Importar minha própria lista") | Adicionar lista (`title` "Adicionar uma nova lista") |
| h1 / `<title>` da tela | Importar lista de canais | Adicionar lista de canais |
| Botão de envio | Importar lista | Gravar |
| Texto acima do grid e `<caption>` | … · ordenados por participantes | … · ordenados por mensagens coletadas |
| Sucesso sem arquivo | — | Lista "X" criada, ainda sem canais. |
| Legenda das tags (nova, escondida em `(hover: none)`) | — | ⓘ Passe o mouse sobre uma lista para ver a descrição |
| Link de volta no topo da tela Adicionar | — | ‹ Editar projeto / ‹ Listas de Canais / ‹ Nova coleta Telegram |

> **Campo arquivo:** no mockup, a área tracejada com o nome do arquivo e o botão "Remover" é só ilustração. A implementação mantém o `ClearableFileInput` nativo via `_telegram_field.html`, sem JS novo. Só mudam o rótulo e o texto de ajuda.
