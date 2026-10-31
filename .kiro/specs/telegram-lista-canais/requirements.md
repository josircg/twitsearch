# Requisitos — Navegação por listas de canais e mensagens do Telegram

## Introdução
Duas novas views no app `telegram`, acessíveis a partir do painel de projetos (`/painel/`):

- `/telegram/lista_canais/` — o usuário escolhe uma ou mais listas de canais (públicas e as suas privadas), exibidas como tags, e vê os canais dessas listas em um grid.
- `/telegram/canal/<id>/` — mensagens coletadas de um canal, lidas do datalake PostgreSQL, com filtro por período e por termo.

## Requisitos

### 1. Acesso a partir do painel
**User story:** Como pesquisador, quero ir das minhas coletas Telegram para os canais monitorados.

Critérios de aceite:
1. O painel (`/painel/`, "Meus projetos") SHALL exibir o botão **"Listas de Canais"** na mesma barra do botão "Nova coleta Telegram".
2. O botão SHALL apontar para `/telegram/lista_canais/` (`{% url 'lista_canais' %}`).

> Interpretação: "visualização dos projetos do Telegram" foi lida como o painel `/painel/`, que é hoje a única tela que lista os projetos do usuário.

### 2. Acesso restrito
**User story:** Como usuário, quero que as telas só estejam disponíveis autenticado.

Critérios de aceite:
1. WHEN um usuário não autenticado acessa `/telegram/lista_canais/` ou `/telegram/canal/<id>/` THEN o sistema SHALL redirecioná-lo para o login (`/admin/login/`).
2. WHEN um usuário autenticado acessa `/telegram/lista_canais/` THEN o sistema SHALL responder com status 200.

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
3. O número de mensagens SHALL ser um link para `/telegram/canal/<Canal.pk>/`.
4. Números SHALL ser formatados com separador de milhar (padrão pt-BR).
5. O grid SHALL ser ordenado por `num_participantes` decrescente e depois por `username`.
6. O grid SHALL ser paginado em 50 canais por página, preservando a seleção de listas na navegação entre páginas.
7. Acima do grid SHALL aparecer o total de canais encontrados.
8. Canais com status diferente de Ativo SHALL aparecer com indicação visual do status (ex.: "Não existe mais").
9. WHEN as listas selecionadas não têm canais THEN o sistema SHALL exibir "Nenhum canal nas listas selecionadas".

### 5. Mensagens do canal
**User story:** Como pesquisador, quero ler as mensagens coletadas de um canal e filtrá-las.

Critérios de aceite:
1. `/telegram/canal/<id>/` SHALL usar `id` = chave primária de `Canal`.
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

## Fora de escopo
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
5. **Rotas.** As novas views seguem o prefixo `telegram/`; `telegram_project/` continua na raiz (Pendência 4 de `telegram-projeto`).
