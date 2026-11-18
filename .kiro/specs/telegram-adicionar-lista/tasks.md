# Tarefas — Adicionar lista de canais (com descrição)

Os blocos A–D podem ser feitos em paralelo. O bloco E depende de todos. Cada tarefa cita os requisitos que atende.

## A. Modelo, migração e admin
- [x] A1. Adicionar `descricao = models.TextField('Descrição', blank=True)` em `Lista` (`telegram/models.py`). _Req. 1.1_
- [x] A2. Gerar `telegram/migrations/0007_lista_descricao.py` com `manage.py makemigrations telegram` e conferir que só contém o `AddField`. _Req. 1.2_
- [x] A3. `ListaAdmin.fields = ('nome', 'publica', 'descricao')`. _Req. 1.3_

## B. Formulário, importação, view e rotas
- [x] B1. Renomear `ImportListaForm` para `AdicionarListaForm`. Incluir `descricao` (Textarea, opcional). Tornar `arquivo` opcional, com o rótulo e a ajuda novos. `clean_arquivo` passa a aceitar `None`. _Req. 2.4, 2.9_
- [x] B2. Adicionar o parâmetro `descricao=''` em `importa_lista` e gravá-lo no `Lista.objects.create`. _Req. 2.7_
- [x] B3. Renomear `importar_lista` para `adicionar_lista` em `telegram/views.py`:
  - caminho sem arquivo (lista vazia + mensagem nova);
  - regra de volta `projeto` > `origem=listas` > padrão, com `voltar_url` e `voltar_rotulo` no contexto;
  - template `adicionar_lista.html`.

  _Req. 2.6, 2.8, 3.1–3.4_
- [x] B4. Em `lista_canais`:
  - incluir `descricao` em cada item;
  - trocar `importar_url` por `adicionar_url = reverse('adicionar_lista') + '?origem=listas'`.

  _Req. 4.1, 5.1_
- [x] B6. Em `lista_canais`, mudar a ordenação para `('-num_mensagens', '-num_participantes', 'username')`. _Req. 7.1_
- [x] B5. Em `core/urls.py`:
  - criar a rota `telegram/listas/adicionar/` (`adicionar_lista`);
  - trocar `telegram/listas/importar/` por um `RedirectView` 301 com `query_string=True`;
  - apontar `telegram_project/importar_lista/` para `adicionar_lista`;
  - atualizar o import.

  _Req. 2.1–2.3_

## C. Templates
- [x] C1. `git mv templates/importar_lista.html templates/adicionar_lista.html`, depois:
  - link de volta no topo (`‹ {{ voltar_rotulo }}`, apontando para `voltar_url`, mesmo estilo de `.tc-back`);
  - título e h1 "Adicionar lista de canais";
  - campo `descricao` entre nome e visibilidade;
  - botão de envio "Gravar".

  _Req. 2.4, 2.5_
- [x] C2. Em `templates/lista_canais.html`:
  - botão "Adicionar lista" com ícone +, usando `adicionar_url`;
  - textos dos dois estados vazios;
  - invólucro `.tc-tag-item` com a dica `.tc-dica` e `aria-describedby`;
  - item novo na legenda: "Passe o mouse sobre uma lista para ver a descrição" (classe `.tc-legenda-dica`);
  - remover `.tc-listas-topo` e levar "Limpar seleção" para o fim da legenda (req. 7.4);
  - texto do total e `<caption>`: "ordenados por mensagens coletadas" (req. 7.2);
  - `<script>` de `lista_canais.js`.

  _Req. 4.1–4.3, 5.1–5.6_
- [x] C3. Em `templates/telegram_project.html`, mudar o botão para "Adicionar lista" (ícone +, `title`, `{% url 'adicionar_lista' %}`), mantendo `?projeto=` e `data-confirma-saida`. _Req. 4.4_

## D. CSS e JS
- [x] D1. Em `core/static/css/style.css`, dentro do bloco `#telegram-canais`, criar `.tc-tag-item`, `.tc-dica` (com a seta), `.tc-legenda-dica` e as regras de `(hover: none)` (escondem `.tc-dica` e `.tc-legenda-dica`) e `prefers-reduced-motion`. O contraste do texto da dica deve ficar em pelo menos 4.5:1. _Req. 5.1, 5.3_
- [x] D1b. Compactar o grid: `.tc-grid td` com `8px 16px`, `th` com `10px 16px`, `.col-desc span` com `line-height: 1.4`, `.tc-canal-titulo` sem `margin-top`. Remover as regras `.tc-listas-topo` (desktop e mobile) e alinhar ao centro a `.tc-legenda`. _Req. 7.3, 7.4_
- [x] D2. Criar `core/static/js/lista_canais.js`: Esc esconde a dica da tag focada e o `blur` restaura. _Req. 5.5_

## E. Testes (`telegram/tests.py`)
Siga `.claude/rules/credenciais-nos-testes.md`: senhas e chaves vêm de `twitsearch.test_credentials`, nunca como literal.

- [x] E1. Atualizar os testes que citam a rota ou o texto antigos:
  - `ImportarListaTests.URL` (renomear a classe para `AdicionarListaTests`);
  - `RotasAntigasTests.ROTAS`: `/telegram_project/importar_lista/` → `/telegram/listas/adicionar/`, mais a nova linha `/telegram/listas/importar/`;
  - `test_importar_nao_e_confundida_com_pk`;
  - `TituloTipografiaTests` (h1 "Adicionar lista de canais");
  - os testes das linhas ~261, 266 e 699 (href do botão do projeto);
  - o teste da linha ~855 (`adicionar_url` no contexto);
  - `test_canal_em_duas_listas_aparece_uma_vez` (linha ~883), que hoje espera a ordem por participantes. Passa a criar os canais com `num_mensagens` e esperar a ordem por mensagens (req. 7.1);
  - `TituloTipografiaTests`/`AdicionarListaTests`: o botão de envio passa a ser "Gravar".

  _Req. 6.1_
- [x] E2. Testes novos:
  - POST sem arquivo cria a lista vazia, com descrição, e redireciona com `?lista=`. _Req. 2.6_
  - POST com arquivo grava a descrição. _Req. 2.7_
  - Arquivo sem canais válidos não cria a lista. _Req. 2.8_
  - `?origem=listas` → Voltar e redirect para `/telegram/listas/?lista=<pk>`. `?projeto=` vence `?origem=`. Um `origem` inválido cai no padrão. O `voltar_rotulo` acompanha a origem. _Req. 3_
  - Em `lista_canais`:
    - tag com descrição tem `aria-describedby` e `role="tooltip"`;
    - tag sem descrição não tem nenhum dos dois;
    - a descrição aparece só dentro da `.tc-dica`, nenhuma vez fora dela.

    _Req. 5.2, 5.4, 5.6_
  - `ListaAdmin` expõe `descricao`. _Req. 1.3_
- [x] E3. Rodar `python manage.py test telegram` e depois a suíte inteira.
