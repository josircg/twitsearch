# Requisitos — Navegação por listas de canais e mensagens do Telegram

## Introdução
Três novas views no app `telegram`, acessíveis a partir do painel de projetos (`/painel/`). Os caminhos seguem o padrão REST do req. 10; os antigos redirecionam para os novos.

- `/telegram/listas/` — o usuário escolhe uma ou mais listas de canais (públicas e as suas privadas), exibidas como tags, e vê os canais dessas listas em um grid.
- `/telegram/canais/<id>/` — mensagens coletadas de um canal, lidas do datalake PostgreSQL, com filtro por período e por termo.
- `/telegram/projetos/<id>/editar/` — edição de um projeto de coleta Telegram, aberta ao clicar no projeto no painel.

## Requisitos

### 1. Acesso a partir do painel
**User story:** Como pesquisador, quero ir das minhas coletas Telegram para os canais monitorados.

Critérios de aceite:
1. O painel (`/painel/`, "Meus projetos") SHALL exibir o botão **"Listas de Canais"** na mesma barra do botão "Nova coleta Telegram".
2. O botão SHALL apontar para `/telegram/listas/` (`{% url 'lista_canais' %}`).

> Interpretação: "visualização dos projetos do Telegram" foi lida como o painel `/painel/`, que é hoje a única tela que lista os projetos do usuário.

### 2. Acesso restrito
**User story:** Como usuário, quero que as telas só estejam disponíveis autenticado.

Critérios de aceite:
1. WHEN um usuário não autenticado acessa `/telegram/listas/` ou `/telegram/canais/<id>/` THEN o sistema SHALL redirecioná-lo para o login (`/admin/login/`).
2. WHEN um usuário autenticado acessa `/telegram/listas/` THEN o sistema SHALL responder com status 200.

### 3. Listas como tags
**User story:** Como pesquisador, quero escolher quais listas de canais quero ver.

Critérios de aceite:
1. A view SHALL exibir, horizontalmente e com quebra de linha, uma tag por lista visível ao usuário: listas com `publica=True` e listas privadas cujo `dono` é o usuário logado, ordenadas por nome.
2. Cada tag SHALL mostrar o nome da lista, o total de canais e um indicador de visibilidade (pública/privada).
3. WHEN o usuário clica em uma tag não selecionada THEN ela SHALL passar a selecionada; WHEN clica em uma tag selecionada THEN ela SHALL deixar de ser selecionada. Mais de uma lista pode estar selecionada ao mesmo tempo.
4. A seleção SHALL ficar na URL (`?lista=<id>&lista=<id>`), permitindo recarregar e compartilhar o link.
5. Ids de lista inexistentes ou de listas privadas de outro usuário SHALL ser ignorados silenciosamente (não exibem canais nem geram erro).
6. WHEN nenhuma lista está selecionada THEN o sistema SHALL exibir uma orientação ("Selecione uma ou mais listas para ver os canais") no lugar do grid.
7. WHEN o usuário não tem nenhuma lista visível THEN o sistema SHALL exibir mensagem informando e um link para importar lista (`importar_lista`).
8. SHALL existir um atalho "Limpar seleção" quando houver lista selecionada.

### 4. Grid de canais
**User story:** Como pesquisador, quero ver os canais das listas escolhidas com seus números.

Critérios de aceite:
1. O grid SHALL exibir a união dos canais das listas selecionadas, sem repetição (um canal presente em duas listas aparece uma vez).
2. Colunas: **Canal** (`username`, com `titulo` como texto secundário e link externo para `https://t.me/<username>`), **Descrição** (`sobre`, truncada), **Participantes** (`num_participantes`) e **Mensagens coletadas** (`num_mensagens`).
3. O número de mensagens SHALL ser um link para `/telegram/canais/<Canal.pk>/`.
4. Números SHALL ser formatados com separador de milhar (padrão pt-BR).
5. O grid SHALL ser ordenado por `num_participantes` decrescente e depois por `username`.
6. O grid SHALL ser paginado em 50 canais por página, preservando a seleção de listas na navegação entre páginas.
7. Acima do grid SHALL aparecer o total de canais encontrados.
8. Canais com status diferente de Ativo SHALL aparecer com indicação visual do status (ex.: "Não existe mais").
9. WHEN as listas selecionadas não têm canais THEN o sistema SHALL exibir "Nenhum canal nas listas selecionadas".

### 5. Mensagens do canal
**User story:** Como pesquisador, quero ler as mensagens coletadas de um canal e filtrá-las.

Critérios de aceite:
1. `/telegram/canais/<id>/` SHALL usar `id` = chave primária de `Canal`.
2. WHEN o canal não existe ou não pertence a nenhuma lista visível ao usuário (pública ou dele) THEN o sistema SHALL responder 404.
3. O cabeçalho SHALL exibir `username`, `titulo`, `sobre`, **Participantes** (`num_participantes`), **Mensagens coletadas** (`num_mensagens`), **Última coleta** (`dt_ultima_carga`) e um link "Voltar às listas" que preserva a seleção anterior quando disponível. Nenhum outro total é exibido (ver "Origem dos números" no design).
4. O formulário de filtro (GET) SHALL ter **Data inicial**, **Data final** e **Termo**; todos opcionais.
5. WHEN a Data final é anterior à Data inicial THEN o sistema SHALL exibir erro no campo e não consultar o datalake.
6. As datas SHALL ser interpretadas no fuso `America/Sao_Paulo`; a Data final inclui o dia inteiro (até 23:59:59).
7. O termo SHALL filtrar mensagens cujo texto contém o termo, sem diferenciar maiúsculas/minúsculas (busca por substring). Conectivos `AND`/`OR` NÃO são interpretados nesta entrega.
8. Cada mensagem SHALL exibir data/hora (no fuso local), texto (com quebras de linha preservadas e o termo destacado), visualizações, encaminhamentos, tipo de mídia (quando houver) e link para `https://t.me/<username>/<message_id>`.
9. Mensagens sem texto (apenas mídia) SHALL aparecer com indicação "[mídia sem texto]".
10. As mensagens SHALL ser ordenadas da mais recente para a mais antiga.
11. Acima da lista SHALL aparecer o total de mensagens encontradas com os filtros aplicados.

### 6. Paginação das mensagens
**User story:** Como pesquisador, quero navegar por milhares de mensagens de um canal sem que a página fique lenta ou gigante.

Critérios de aceite:
1. A lista de mensagens SHALL ser paginada no servidor: cada requisição busca no datalake apenas as mensagens da página atual. Canais podem ter milhares de mensagens coletadas.
2. O tamanho da página SHALL ser selecionável entre **25** (padrão), **50** e **100**, via parâmetro `por_pagina`; outros valores SHALL cair no padrão.
3. A página atual SHALL vir do parâmetro `page`; valores ausentes, não numéricos ou menores que 1 SHALL resultar na página 1, e valores acima da última página SHALL resultar na última página.
4. Acima da lista SHALL aparecer: total encontrado, seletor "Por página" e navegação compacta (anterior / "Página X de Y" / próxima).
5. Abaixo da lista SHALL aparecer: "Mostrando A–B de N", botões **Anterior** e **Próxima** (desabilitados na primeira/última página), números de página com reticências (sempre a primeira, a última e as vizinhas da atual) e campo **"Ir para a página"**.
6. Todos os links de paginação SHALL preservar os filtros (`dt_inicio`, `dt_final`, `termo`), o `por_pagina` e o `voltar`.
7. WHEN qualquer filtro ou o tamanho da página muda THEN a navegação SHALL voltar para a página 1.
8. Números (total, faixa, páginas) SHALL usar separador de milhar pt-BR.
9. No celular, a navegação SHALL se reduzir a Anterior / "Página X de Y" / Próxima e "Ir para", com alvos de toque de pelo menos 44px.
12. WHEN o canal ainda não tem `id_numerico` (não sincronizado) THEN o sistema SHALL exibir "Canal ainda não sincronizado; as mensagens aparecerão após a próxima coleta" sem consultar o datalake.
13. WHEN não há mensagens para os filtros THEN o sistema SHALL exibir "Nenhuma mensagem encontrada" e manter os filtros preenchidos.
14. WHEN o datalake está indisponível THEN o sistema SHALL exibir mensagem de erro amigável (status 200, sem traceback) e registrar o erro no log.
15. As mensagens SHALL ser exibidas em lista compacta (um único cartão, linhas separadas por divisória): à esquerda, uma coluna estreita com a data/hora e, logo abaixo, visualizações, encaminhamentos e link para o Telegram (ícone); à direita, tipo de mídia + texto ocupando o restante da largura. No celular, data e métricas ficam numa única linha acima do texto.

### 7. Edição do projeto
**User story:** Como pesquisador, quero clicar em um projeto no painel e ajustar seus dados (nome, descrição, lista, período, termos) sem precisar do admin.

Critérios de aceite:
1. No painel (`/painel/`), o nome de cada projeto que inclui a rede Telegram SHALL ser um link para `/telegram/projetos/<Projeto.pk>/editar/` (`{% url 'editar_projeto' projeto.pk %}`). Projetos sem a rede Telegram SHALL continuar exibindo o nome como texto.
2. WHEN um usuário não autenticado acessa `/telegram/projetos/<id>/editar/` THEN o sistema SHALL redirecioná-lo para o login (`/admin/login/`).
3. WHEN o projeto não existe, não pertence ao usuário logado (`Projeto.usuario`) ou não inclui a rede Telegram THEN o sistema SHALL responder 404.
4. A tela SHALL ter o título **"Editar projeto"** e um link "Meus projetos" de volta ao painel.
5. O formulário SHALL ter os mesmos campos, rótulos, ajudas e validações da criação (req. 2 e 3 de `telegram-projeto`) e SHALL vir preenchido:
   - Nome, Descrição Breve da Pesquisa (`objetivo`) e Lista de canais (`lista_canais`) do `Projeto`;
   - Data Inicial = menor `Termo.dtinicio` e Data Final = maior `Termo.dtfinal` dos termos ativos, convertidas para data no fuso `America/Sao_Paulo`;
   - Termos de busca = `Termo.busca` dos termos ativos, um por linha, na ordem de criação.
6. A Lista de canais SHALL oferecer as listas visíveis ao usuário (req. 3.1) e, mesmo que deixe de ser visível, a lista atual do projeto.
7. WHEN o usuário clica em **"Salvar alterações"** e o formulário é válido THEN o sistema SHALL, em uma única transação:
   1. atualizar `nome`, `objetivo` e `lista_canais` do `Projeto` (o `status` do projeto não é editado nesta tela);
   2. manter os termos cuja linha é idêntica (após remover espaços nas pontas) a um termo existente do projeto, preservando o que já foi coletado (`last_count`, `TermoStatus`, ponteiros);
   3. criar `Termo` + `TermoStatus` (rede Telegram) para cada linha nova, como na criação;
   4. marcar como Interrompido (`status = 'X'` em `Termo` e no seu `TermoStatus`) os termos ativos que não aparecem mais no campo. Termos NÃO SHALL ser excluídos (há dados coletados ligados a eles);
   5. reativar (`status = 'A'`) um termo interrompido cuja linha volte a ser informada;
   6. gravar Data Inicial e Data Final (início e fim do dia) em todos os termos ativos após a edição.
8. WHEN a gravação conclui THEN o sistema SHALL exibir "Projeto atualizado." e redirecionar para `/painel/`.
9. WHEN o formulário é inválido THEN o sistema SHALL reexibir a tela com os valores digitados e os erros, sem gravar nada.
10. **"Cancelar"** SHALL voltar ao painel sem gravar.
11. Abaixo do campo de termos SHALL aparecer o aviso: "Termos removidos deixam de ser coletados; o que já foi coletado é mantido."

### 8. Importar lista a partir da edição
**User story:** Como pesquisador editando um projeto, quero importar uma lista nova e voltar para o mesmo projeto com ela selecionada.

Critérios de aceite:
1. Na tela de edição, o botão "Importar lista" SHALL apontar para `/telegram/listas/importar/?projeto=<Projeto.pk>`. Na criação, continua sem parâmetro.
2. WHEN a importação recebe `projeto` de um projeto editável pelo usuário (req. 7.3) THEN:
   1. o link "Voltar" da importação SHALL levar à edição desse projeto;
   2. ao concluir a importação, o sistema SHALL redirecionar para `/telegram/projetos/<id>/editar/?lista=<id da nova lista>`, com a mesma mensagem de totais de hoje.
3. WHEN `projeto` é inválido, de outro usuário ou de projeto sem Telegram THEN a importação SHALL ignorá-lo silenciosamente e se comportar como hoje (volta para a criação).
4. A tela de edição SHALL aceitar `?lista=<id>` e pré-selecionar essa lista no lugar da lista atual do projeto, desde que ela seja uma opção válida do campo; caso contrário, mantém a lista atual. A lista só é gravada ao "Salvar alterações".
5. WHEN o usuário clica em "Importar lista" com alterações não salvas no formulário de edição THEN o navegador SHALL pedir confirmação ("Você tem alterações não salvas neste projeto. Sair para importar uma lista mesmo assim?"); cancelar mantém o usuário na tela. Sem alterações, navega direto.

### 9. Estados de erro do formulário de projeto (no navegador)
**User story:** Como pesquisador, quero ver os erros enquanto preencho, como no protótipo, sem precisar enviar o formulário para descobrir o que está errado.

Vale para o formulário de projeto Telegram nos dois modos (criação e edição), que usam o mesmo template.

Critérios de aceite:
1. O navegador SHALL validar os campos com as mesmas regras e as mesmas mensagens do servidor:
   - Nome do Projeto, Descrição, Lista de canais, Data Inicial, Data Final e Termos obrigatórios: "Este campo é obrigatório.";
   - Data Final anterior à Data Inicial: "A data final não pode ser anterior à data inicial." (no campo Data Final);
   - nenhum termo: "Informe ao menos um termo de busca.";
   - termo com mais de 2000 caracteres: "Termo muito longo (máximo 2000 caracteres): <início do termo>...";
   - `AND`/`OR` no início, no fim ou consecutivos: "Uso inválido de AND/OR no termo: <termo>".
2. Cada campo SHALL ser validado ao ser alterado (`input`/`change`) depois de ter sido tocado, e todos os campos SHALL ser validados ao clicar no botão de envio. Campo vazio ainda não tocado não mostra erro.
3. Campo com erro SHALL ter borda vermelha (`#D92D20`), `aria-invalid="true"` e a mensagem logo abaixo, em vermelho (`#B42318`), ligada ao campo por `aria-describedby`. Corrigido o valor, o erro SHALL sumir na hora.
4. Enquanto houver erro visível, o sistema SHALL:
   1. exibir acima do formulário o alerta "Corrija os campos destacados para salvar." (`role="alert"`);
   2. desabilitar o botão de envio ("Salvar alterações" / "Iniciar a coleta") com `aria-disabled="true"`, opacidade reduzida e cursor de bloqueio.
   Sem erros, o alerta some e o botão volta a funcionar.
5. Um clique no botão com erros não visíveis (campos vazios não tocados) SHALL exibir todos os erros, mover o foco para o primeiro campo inválido e não enviar o formulário.
6. Erros vindos do servidor (formulário reexibido após POST) SHALL aparecer com o mesmo visual (borda, mensagem, alerta e botão desabilitado) e SHALL sumir assim que o campo é corrigido.
7. O servidor continua validando tudo; sem JavaScript, o formulário funciona como hoje (validação só no envio).

### 10. Rotas no padrão REST
**User story:** Como mantenedor, quero rotas previsíveis, sem `_`, organizadas por recurso.

Critérios de aceite:
1. As telas SHALL usar caminhos em minúsculas, sem `_`, com o recurso no plural e as ações `novo`, `editar` e `importar` como sufixo:

   | Tela | Antes | Depois | Nome da rota |
   |---|---|---|---|
   | Nova coleta Telegram | `/telegram_project/` | `/telegram/projetos/novo/` | `telegram_project` |
   | Editar projeto | `/telegram_project/<id>/` | `/telegram/projetos/<id>/editar/` | `editar_projeto` |
   | Importar lista | `/telegram_project/importar_lista/` | `/telegram/listas/importar/` | `importar_lista` |
   | Listas de Canais | `/telegram/lista_canais/` | `/telegram/listas/` | `lista_canais` |
   | Mensagens do canal | `/telegram/canal/<id>/` | `/telegram/canais/<id>/` | `canal_mensagens` |
   | Importação de canais (admin) | `/telegram/importacao_canais/` | `/telegram/canais/importar/` | `importacao_canais` |
   | Importação de tweets (admin) | `/importacao_arquivo/` | `/tweets/importar/` | `importacao_arquivo` |
   | Status do termo (admin) | `/termo_stat/<id>` | `/termos/<id>/status/` | `status_coleta` |

   `canal/` vira `canais/` (plural) para seguir o mesmo padrão, mesmo sem `_`.
2. Os nomes das rotas (`name=`) SHALL ser mantidos, para que `{% url %}` e `reverse()` continuem funcionando sem mudança.
3. Todo caminho antigo da tabela SHALL redirecionar permanentemente (301) para o novo, preservando os parâmetros e a query string (ex.: `/telegram/canal/37/?voltar=lista%3D2` → `/telegram/canais/37/?voltar=lista%3D2`).
4. Nenhum caminho SHALL ficar escrito à mão no código; o link do admin para o status do termo SHALL usar `reverse('status_coleta', ...)`.
5. As rotas de API (`/api/...`), usadas por consumidores externos como o `vtrack-consumidor`, NÃO SHALL mudar.

### 11. Tipografia conforme o protótipo
**User story:** Como pesquisador, quero que o painel, o formulário de projeto, a importação de lista, as listas de canais e as mensagens do canal tenham a mesma tipografia do protótipo aprovado, para que as telas pareçam um só produto.

Vale para: `/painel/`, `/telegram/projetos/<id>/editar/`, `/telegram/projetos/novo/`, `/telegram/listas/importar/`, `/telegram/listas/` e `/telegram/canais/<id>/`, em desktop (1280px) e celular (390px). Não vale para o cabeçalho e o rodapé de `base.html`, nem para páginas fora desta entrega (início, admin, login).

> Interpretação: a fonte da verdade é a versão atual do protótipo publicado (https://claude.ai/artifact/MFVvasjD7cU8ZZ8gdurZ4r): telas `Painel`, `EditarProjeto`, `Main`, `Canal`, `ListaMobile` e `CanalMobile`, já com a lista de mensagens compacta (req. 6.15). Versões antigas das telas de listas e mensagens (cartões de 15px, "Total no Telegram") NÃO valem. A medição de 31/10/2026 (Chrome, `getComputedStyle` nas views reais) mostrou que listas de canais e mensagens já coincidem com o protótipo; as divergências estão nos títulos `h1`, no formulário de projeto (criação, edição e importação), em dois `strong`, em três ajustes de celular e em detalhes do painel. A coluna "Hoje" abaixo registra o valor medido onde difere do alvo.
>
> Não há artboard de celular para painel, edição, criação e importação: os valores de desktop valem também no celular.

Critérios de aceite:
1. Todo texto das seis telas SHALL usar a família Poppins (`'Poppins', sans-serif`), inclusive `input`, `select`, `textarea` e `button`; o corpo continua em 16px / line-height 1.5. Onde o protótipo não define `line-height`, vale o `normal` do Poppins, que equivale a 1.5 (diferença de até 1px na altura computada é aceita). Hoje a família já está correta em todas as telas.
2. **Títulos.** Cada tela SHALL ter um único título como `<h1>`, com peso 600, cor `#1E1D30` e line-height 1.5:

   | Tela | Desktop | Celular (≤ 767.98px) | Hoje (se diferente) |
   |---|---|---|---|
   | Painel ("Meus projetos") | 24px | 24px | line-height 1.2 |
   | Editar projeto | 24px | 24px | line-height 1.2; cor `#212529` |
   | Nova coleta Telegram | 24px | 24px | é `<h4>`, peso 500, line-height 1.2, cor `#212529`, 21,57px no celular |
   | Importar lista de canais | 24px | 24px | idem Nova coleta Telegram |
   | Listas de Canais | 26px | 22px | line-height 1.2 |
   | Canal (nome) | 26px | 21px | line-height 1.2 |

3. **Formulário de projeto e importação** (criação, edição e importação, que usam o mesmo estilo):

   | Papel | Alvo | Hoje (se diferente) |
   |---|---|---|
   | Link "Meus projetos" (edição) | 14px / 500 / `#0066FF` | — |
   | Rótulo de campo (`label`) | 14px / 600 / `#1E1D30` | 16px |
   | Texto digitado em `input` (texto, data, arquivo), `select` e `textarea` | 15px / 400 / `#1E1D30` | 16px |
   | `textarea` "Termos de busca" | line-height 1.6 | 1.5 |
   | `textarea` "Descrição" | line-height 1.5 | — |
   | Opção de rádio (Visibilidade, importação) | 15px / 400 / `#1E1D30` | 16px; cor `#212529` |
   | Texto de ajuda (`form-text`) | 13px / 400 / `#6B6C72` | 14px |
   | Erro de campo | 13px / 400 / `#B42318` | erro de Visibilidade (importação): 16px, cor do Bootstrap (`text-danger`) |
   | Alerta "Corrija os campos destacados para salvar." | 14px / 400 / `#B42318` | — |
   | Mensagens do sistema (`.alert` de sucesso/erro/aviso) | 14px / 400 | 16px |
   | Aviso informativo (termos removidos) | 13px / 400 / `#1E1D30` | — |
   | Botão "Importar lista" (contorno) | 14px / 500 / `#1E1D30` | 14,4px |
   | Botão primário ("Salvar alterações", "Iniciar a coleta", "Importar lista") | 15px / 600 / `#FFFFFF` | 16px |
   | "Cancelar" / "Voltar" | 15px / 500 / `#6B6C72` | 16px |

   Textos do formulário sem cor própria SHALL herdar `#1E1D30` (e não o `#212529` do Bootstrap).
4. **Painel:**

   | Papel | Alvo | Hoje (se diferente) |
   |---|---|---|
   | Botões de ação ("Nova coleta…", "Listas de Canais", "Admin") | 14px / 500 (contorno: 600) / line-height 1.5 | line-height 1.4 |
   | Cabeçalho da tabela | 12px / 600 / `#6B6C72` / maiúsculas / letter-spacing 0.5px | — |
   | Nome de projeto com link | 14px / 500 / `#0066FF` | — |
   | Nome de projeto sem link (sem rede Telegram) | 14px / 400 / `#4D4D4D` | cor `#1E1D30` |

5. **Listas de canais** (`Main` / `ListaMobile`):

   | Papel | Desktop | Celular | Hoje (se diferente) |
   |---|---|---|---|
   | Link "Meus projetos" | 14px / 400 / `#6B6C72` | 14px | — |
   | Subtítulo | 14px / 400 / `#6B6C72` | 13px | — |
   | Botão "Importar lista" | 14px / 500 / `#1E1D30` | 14px | — |
   | Rótulo "LISTAS" | 13px / 600 / `#6B6C72` / maiúsculas / 0.6px | 12px | — |
   | "Limpar seleção" | 13px / 500 / `#0066FF` | 13px | — |
   | Tag de lista | 14px / 500 | 13px / 500 | — |
   | Selo de total/visibilidade | 12px / 600 | 11px / 600 | — |
   | Legenda (pública/privada) | 12px / 400 / `#6B6C72` | oculta | — |
   | Total de canais | 15px / 400 / `#6B6C72`; destaque (`strong`) 600 / `#1E1D30` | 14px | destaque 700 |
   | Cabeçalho da tabela | 12px / 600 / `#6B6C72` / maiúsculas / 0.5px | oculto | — |
   | `@usuario` do canal | 14px / 600 / `#1E1D30` | 15px | — |
   | Título do canal | 13px / 400 / `#6B6C72` | 12px | — |
   | Descrição | 14px / 400 / `#4A4B57` / line-height 1.5 | 13px | — |
   | Participantes | 14px / 400 / `#1E1D30` | 15px / 600 | — |
   | Link de mensagens | 14px / 600 / `#0066FF` | 15px / 600 | — |
   | Selo de status ("Não existe mais") | 12px / 500 / `#9A4A00` | 11px / 500 | celular: 12px |
   | Estado vazio: título / texto | 16px / 600 / `#1E1D30` e 14px / 400 / `#6B6C72` | idem | — |

6. **Mensagens do canal** (`Canal` / `CanalMobile`):

   | Papel | Desktop | Celular | Hoje (se diferente) |
   |---|---|---|---|
   | Link "Voltar às listas" | 14px / 400 / `#6B6C72` | 14px | — |
   | Link `@usuario` | 14px / 500 / `#0066FF` | 13px | — |
   | Descrição do canal | 14px / 400 / `#4A4B57` / line-height 1.6 | 13px / line-height 1.55 | — |
   | Resumo: rótulo (`dt`) | 12px / 400 / `#6B6C72` | 11px | — |
   | Resumo: valor (`dd`) | 20px / 600 | 15px / 600 | — |
   | Resumo: última coleta | 15px / 600 / line-height 1.9 | 13px / 600 / line-height 1.75 | — |
   | Rótulo dos filtros | 14px / 600 | 13px / 600 | — |
   | Campos dos filtros | 14px / 400 / `#1E1D30` | 14px | — |
   | "Filtrar" / "Limpar" | 14px / 600 `#FFFFFF` e 14px / 500 `#6B6C72` | 14px | — |
   | Erro de campo | 13px / 400 / `#B42318` | 13px | — |
   | Total de mensagens | 15px / 400 / `#6B6C72`; destaque (`strong`) 600 / `#1E1D30` | 14px; faixa "51–75" 12px | destaque 700 (desktop e celular) |
   | "Por página" e seletor | 14px / 400 | oculto | — |
   | Data/hora da mensagem | 12px / 500 / `#4A4B57` | 11px / **400** / **`#6B6C72`** | celular: 500 / `#4A4B57` |
   | Visualizações, encaminhamentos | 12px / 400 / `#6B6C72` | 11px (com "vis." e "enc.") | — |
   | Link "Telegram ↗" | ícone | 11px / 500 / `#0066FF` | — |
   | Tipo de mídia (selo) | 11px / 500 / `#4A5568` | 10px / 500 | — |
   | Texto da mensagem e destaque (`mark`) | 14px / 400 / `#1E1D30` / line-height 1.5 | 13px | — |
   | "[mídia sem texto]" | 14px / itálico / `#6B6C72` | 13px | — |
   | Paginação (resumo, botões, números) | 14px / 400; página atual 600 / `#FFFFFF`; faixa em destaque 600 / `#1E1D30` | 14px | — |
   | "Ir para a página" | 14px / 400 / `#6B6C72` | "Ir para" 13px | — |
   | Botão "Ir" | 14px / 600 / `#0066FF` | 13px / 600 | celular: 14px |
   | Estados vazio e não sincronizado: título / texto | 16px / 600 e 14px / 400 / `#6B6C72` | idem | — |
   | Alerta do datalake: título / texto | 15px / 600 e 14px / 400, ambos `#7A1A10` | idem | — |

7. Destaques `strong` SHALL ter peso 600 no total de canais e no total de mensagens (nos dois tamanhos de tela). O "3" de "Página **3** de 195" (navegação compacta) SHALL continuar em 700, como no protótipo.
8. Os valores da coluna "Celular" SHALL valer em larguras ≤ 767.98px (o mesmo ponto de quebra já usado em `#telegram-canais`). Painel, criação, edição e importação não mudam de tamanho no celular.
9. Desvios aceitos, que NÃO fazem parte desta entrega (registrados para decisão do usuário):
   1. o status do projeto no painel continua como selo (12px / 500, verde "Ativo" / laranja "Inativo"); o protótipo mostra texto simples de 14px / 400;
   2. o rodapé de paginação da lista de canais (`_paginacao.html`) continua com 14px, igual ao do canal; o artboard `Main` usa 13px e círculos de 36px;
   3. o subtítulo "Coleta Telegram · criado em …" do artboard de edição e a nota "Mensagens = total informado pelo Telegram" do artboard antigo da lista são conteúdo, não tipografia, e não são implementados aqui.
10. WHEN a tipografia é ajustada THEN o sistema NÃO SHALL alterar o cabeçalho e o rodapé de `base.html`, a página inicial, o admin nem regras globais de `h1`–`h6`, `strong` ou `.alert`: as mudanças SHALL ficar nos blocos escopados `#painel`, `#telegram-project` e `#telegram-canais`.
11. WHEN as seis telas são renderizadas em 1280px e em 390px THEN `getComputedStyle` dos elementos das tabelas 2 a 6 SHALL coincidir com o alvo (família Poppins; tamanho, peso, cor, itálico, maiúsculas e letter-spacing exatos; line-height com diferença de até 0,08 em razão do tamanho da fonte).
12. WHEN o tamanho dos campos e botões do formulário diminui de 16px para 15px THEN a altura de `input`, `select` e dos botões primários SHALL continuar em 46px (altura do protótipo), e nenhuma tela SHALL ganhar rolagem horizontal em 390px.
13. Os links de voltar das telas de listas e de mensagens ("Meus projetos" em `/telegram/listas/` e "Voltar às listas" em `/telegram/canais/<id>/`) SHALL usar o azul de link do sistema (`#0066FF`, peso 500; `#0052CC` no hover), como o "Meus projetos" da edição de projeto. Hoje: cinza `#6B6C72`, peso 400.

## Fora de escopo
- Exclusão de projetos e edição de projetos de outras redes (Youtube, Twitter).
- Renomear as ações e downloads antigos do Twitter que não são telas (`solicita_busca`, `backup_json`, `exclui_json`, `solicitar_csv`, `gerar_gephi`) e as rotas `/api/...`.
- Edição de listas (adicionar/remover canais) nestas telas — continua no admin e na importação.
- Busca com conectivos `AND`/`OR` e busca full-text com stemming.
- Exportação (CSV) das mensagens filtradas.
- Exibição de mídia (imagens/documentos) — só o tipo é mostrado.
- Mensagens ainda não exportadas para o datalake.

## Pendências (em aberto — fora desta entrega)
1. **Números do `Canal` são aproximados.** `num_participantes` é gravado só uma vez, pelo `sync_channels` (que processa apenas canais sem `id_numerico`), e não é mais atualizado. `num_mensagens` é a soma do que o `get_messages` capturou desde `DATA_LIMITE`; conta antes da exportação para o datalake e não soma os lotes gravados quando a coleta do canal é interrompida no meio. Por isso pode divergir do total exibido na página do canal (contagem no datalake). Avaliar: atualizar participantes periodicamente e salvar `num_mensagens` a cada lote.
   - **Situação em 31/10/2026: todos os canais estão com 0 participantes.** Os 185 canais foram sincronizados em 03/09/2026; a leitura de `full_chat.participants_count` só entrou no `sync_channels` em 05/09/2026 (commit 85b60fb). Antes disso só se lia `entity.participants_count`, que o Telegram devolve vazio (`None` → `or 0`). Como o `sync_channels` só processa canais sem `id_numerico`, eles nunca foram ressincronizados.
   - A coleta lê cada canal em ordem cronológica a partir de `DATA_LIMITE` (01/01/2025), no máximo `--limite` (padrão 1000) mensagens por execução; com a última carga em 03/09/2026, vários canais só têm mensagens até o início de 2025. A página do canal mostra o período coletado quando um filtro de datas não encontra nada.
2. **Latência de exportação.** As mensagens só aparecem depois que `export_telegram` processa os JSON de `data/telegram/`.
3. **Índice no datalake.** A tabela `telegram` é externa (não gerenciada por migrations); o índice por canal + data precisa ser aplicado manualmente em produção.
4. **Conectivos no filtro por termo.** Reaproveitar a sintaxe `AND`/`OR` de `TelegramProjectForm` quando a coleta passar a aplicá-la (Pendência 1 de `telegram-projeto`).
6. **Tabela `telegram` é `UNLOGGED`.** O PostgreSQL esvazia tabelas UNLOGGED (`telegram`, `historico`) após um desligamento não limpo; a página do canal passa a mostrar "Nenhuma mensagem encontrada" para todos os canais. Ocorreu no docker local em 31/10/2026 (recuperado repovoando `telegram` a partir de `fila_telegram`). Avaliar `ALTER TABLE telegram SET LOGGED` ou um procedimento de recarga.
5. ~~**Rotas.**~~ **(Resolvido — req. 10.)** Todas as telas do Telegram estão sob `telegram/`, no padrão REST.
