# Requisitos — Adicionar lista de canais (com descrição)

## Introdução
Origem: issue #46, "Melhoria na Criação de Listas".

Hoje uma lista de canais só nasce importando um arquivo, em `/telegram/listas/importar/`. Esta spec:

- acrescenta uma descrição à lista;
- troca a tela de importação por uma tela de **adição**, em que o arquivo é opcional;
- troca o botão "Importar lista" por "Adicionar lista" na tela de listas;
- mostra a descrição de cada lista como dica (hint) na própria tag da lista.

Telas envolvidas:

- `/telegram/listas/adicionar/` (nova): substitui `/telegram/listas/importar/`.
- `/telegram/listas/`: tela de listas de canais (`lista_canais`).
- `/telegram/projetos/novo/` e `/telegram/projetos/<id>/editar/`: o botão ao lado do campo "Lista de canais" passa a abrir a nova tela.

Mockups: canvas "Capitu — Listas de Canais Telegram", página **"Issue #46 — Adicionar lista"** (link em `design.md`).

## Requisitos

### 1. Descrição da lista
**User story:** Como pesquisador, quero registrar um comentário sobre a lista que criei, para lembrar (e mostrar aos outros) o que ela reúne.

Critérios de aceite:
1. O modelo `Lista` SHALL ter o campo `descricao` (`TextField`, rótulo "Descrição", `blank=True`, padrão vazio).
2. Listas já existentes SHALL continuar válidas após a migração, com descrição vazia.
3. O admin de listas (`ListaAdmin`) SHALL exibir e permitir editar `descricao`, depois de `nome` e `publica`.

### 2. Tela "Adicionar lista" no lugar de "Importar lista"
**User story:** Como pesquisador, quero criar uma lista mesmo sem ter um arquivo de canais em mãos.

Critérios de aceite:
1. O sistema SHALL responder em `/telegram/listas/adicionar/` (nome de rota `adicionar_lista`), só para usuários autenticados.
2. WHEN alguém acessa `/telegram/listas/importar/` THEN o sistema SHALL redirecioná-lo com 301 para `/telegram/listas/adicionar/`, preservando a query string.
3. A rota antiga `/telegram_project/importar_lista/` SHALL redirecionar (301) direto para `/telegram/listas/adicionar/`, preservando a query string.
4. O formulário SHALL ter, nesta ordem:
   - **Nome da lista** (obrigatório, até 100 caracteres);
   - **Descrição** (textarea, opcional);
   - **Visibilidade** (privada/pública, igual a hoje);
   - **Arquivo de canais** (CSV ou Excel, opcional).
5. O título da tela (h1) SHALL ser "Adicionar lista de canais", e o botão de envio SHALL ser **"Gravar"**.
6. WHEN o usuário envia sem arquivo THEN o sistema SHALL criar a lista vazia, com nome, descrição e visibilidade, e exibir: `Lista "<nome>" criada, ainda sem canais.`
7. WHEN o usuário envia com arquivo THEN o sistema SHALL se comportar como a importação atual, gravando também a descrição. A mensagem de sucesso continua a mesma.
8. WHEN o arquivo enviado não tem nenhum canal válido, ou é ilegível, THEN o sistema SHALL recusar o envio com erro no campo arquivo e SHALL NOT criar a lista. Assim, "lista vazia" só acontece quando o usuário opta por não enviar arquivo.
9. As validações atuais SHALL continuar valendo:
   - nome repetido entre as listas do mesmo dono;
   - extensão `.csv`/`.xlsx`;
   - limite de `MAX_LINHAS`;
   - visibilidade obrigatória.

> Interpretação: "substituir a view" foi lida como renomear a rota e a view, mantendo o mesmo formulário. A URL antiga não quebra: ela redireciona, no padrão já usado nas outras rotas antigas (`RotasAntigasTests`).

### 3. Para onde o usuário volta
**User story:** Como pesquisador, quero voltar à tela de onde vim depois de criar a lista, já com ela selecionada.

Critérios de aceite:
1. WHEN a tela é aberta com `?projeto=<id>` de um projeto editável pelo usuário THEN "Voltar" e o redirecionamento pós-criação SHALL ir para a edição desse projeto, com `?lista=<nova>` após criar (igual a hoje).
2. WHEN a tela é aberta com `?origem=listas` THEN "Voltar" SHALL ir para `/telegram/listas/` e, após criar, o sistema SHALL redirecionar para `/telegram/listas/?lista=<nova>`, com a nova lista já selecionada.
3. Sem nenhum desses parâmetros, o destino SHALL continuar sendo `/telegram/projetos/novo/` (`?lista=<nova>` após criar), como hoje.
4. Valores inválidos de `origem` SHALL ser ignorados e valer como ausentes.
5. Acima do título, a tela SHALL ter um link de volta (seta "‹") para o mesmo destino do "Voltar". O rótulo segue a origem: "Editar projeto", "Listas de Canais" ou "Nova coleta Telegram".

> Interpretação: hoje o botão "Importar lista" da tela de listas leva para a importação **sem** contexto, e o usuário cai em "Nova coleta Telegram" ao terminar. A issue não pede para mudar isso, mas com o botão novo esse desvio ficaria mais visível. Por isso a spec inclui o retorno à tela de listas.

### 4. Botão "Adicionar lista" na tela de listas
**User story:** Como pesquisador, quero que o botão da tela de listas diga o que ele faz agora.

Critérios de aceite:
1. Na tela `/telegram/listas/`, o botão do cabeçalho SHALL ter o rótulo **"Adicionar lista"**, ícone "+" no lugar da seta de upload, e apontar para `/telegram/listas/adicionar/?origem=listas`.
2. O estado "Você ainda não tem listas de canais." SHALL oferecer o link **"Adicionar uma lista"**, com o mesmo destino.
3. O estado "Nenhum canal nas listas selecionadas" SHALL deixar de sugerir "importe um arquivo", porque esse link criaria outra lista em vez de preencher a atual. O texto passa a ser: "As listas selecionadas ainda não têm canais. Fale com o administrador para incluí-los."
4. No formulário de projeto (nova coleta e edição), o botão ao lado do campo "Lista de canais" SHALL passar a se chamar **"Adicionar lista"**, com ícone "+" e `title="Adicionar uma nova lista"`, e apontar para a nova rota. O `?projeto=<id>` e o `data-confirma-saida` continuam como estão.

> Interpretação: a issue escreve "Adicionar Lista". Os botões atuais usam só a inicial maiúscula ("Importar lista"), então o rótulo segue esse padrão: "Adicionar lista".
>
> Interpretação: a issue fala só da tela de listas. O botão do formulário de projeto também muda de nome porque passa a abrir a mesma tela, que não importa mais obrigatoriamente.

### 5. Dica com a descrição da lista
**User story:** Como pesquisador, quero ver a descrição de uma lista antes de selecioná-la.

Critérios de aceite:
1. WHEN o usuário passa o mouse ou foca pelo teclado uma tag de lista que tem descrição THEN o sistema SHALL exibir uma dica (tooltip) acima da tag, com o texto da descrição.
2. A dica SHALL ser associada à tag por `aria-describedby`, para que leitores de tela anunciem a descrição junto com o nome da lista.
3. A dica SHALL mostrar no máximo 4 linhas, até 320 px de largura, e respeitar as quebras de linha digitadas. Descrições mais longas terminam em reticências.
4. Tags de listas sem descrição SHALL NOT ter dica nem `aria-describedby`.
5. A dica SHALL sumir ao tirar o mouse ou o foco, e com a tecla Esc enquanto a tag está focada.
6. A descrição SHALL aparecer **somente** na dica. A tela não exibe a descrição em nenhum outro lugar, para não crescer com listas de descrições longas.

> Interpretação: "hint sobre o botão" foi lido como dica sobre **cada tag de lista**, porque cada lista é um botão-tag e é a descrição *dela* que o usuário quer ver. A dica no botão "Adicionar lista" não teria descrição nenhuma para mostrar.
>
> Em telas de toque não existe hover, então a dica não aparece. Isso foi aceito na revisão do mockup.

### 6. Compatibilidade
Critérios de aceite:
1. Os testes existentes que citam `importar_lista` ou "Importar lista de canais" SHALL ser atualizados para a nova rota e o novo texto. Os demais SHALL continuar passando.
2. A tela de importação de canais do admin (`/telegram/canais/importar/`) SHALL NOT mudar.

### 7. Ajustes na tela de listas (revisão do mockup)
**User story:** Como pesquisador, quero ver mais canais por tela, começando pelos que têm mais mensagens coletadas.

Critérios de aceite:
1. O grid de canais SHALL vir **sempre** ordenado por mensagens coletadas, da maior para a menor. Em caso de empate, por participantes (maior primeiro) e depois por username.
2. O texto acima do grid SHALL dizer "ordenados por mensagens coletadas", e a `<caption>` da tabela também.
3. As linhas do grid SHALL ficar mais compactas:
   - células com `8px 16px` de padding (hoje `14px 20px`), e o cabeçalho com `10px 16px`;
   - descrição do canal com `line-height: 1.4` e no máximo 2 linhas, como hoje.
   O layout em cartões do celular (`max-width: 767.98px`) não muda.
4. O link **"Limpar seleção"** SHALL sair de cima das tags e ficar abaixo delas, à direita, na mesma linha da legenda. A linha de cima, com o rótulo "LISTAS", deixa de existir. O grupo de tags continua com `aria-label="Listas de canais"`.

> Origem: comentários de Josir no canvas, na revisão de 18/11/2026. Os itens 1 a 3 não estão na issue #46, mas entram nesta entrega porque mexem na mesma tela.

## Fora do escopo / pontos em aberto
- **Como incluir canais numa lista vazia.** Pelo usuário comum, hoje não há como: o inline de canais do admin de listas é somente leitura (commit f95019b), e a importação em `/telegram/canais/importar/` é uma tela administrativa. Esta spec só cria a lista vazia. Uma tela para o próprio usuário adicionar canais a uma lista existente fica para outra issue.
- Editar a descrição de uma lista fora do admin.
