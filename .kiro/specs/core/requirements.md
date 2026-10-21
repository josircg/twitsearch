# Requirements Document

_App `core` do Capitu._

> **Natureza deste documento.** Esta é documentação de **engenharia reversa** do
> comportamento atual da app `core` do Capitu, não a especificação de uma feature
> nova. Os requisitos abaixo descrevem o que o sistema faz hoje, para servir de
> referência de manutenção. Pontos de atenção e sugestões de melhoria estão
> reunidos ao final, na seção "Pontos de atenção".

## Introduction

A app `core` é o núcleo do Capitu. Ela concentra:

- a modelagem de domínio (Projeto, Termo, Tweet, Retweet, usuários, etc.);
- a coleta de tweets na API v2 do Twitter/X (via *management commands*);
- a importação dos dados coletados (JSON/XLSX/lista de IDs) para o banco MySQL;
- a busca na base local já coletada;
- a exportação em CSV (tags/Gephi) e a geração de nuvem de palavras e grafo;
- a interface administrativa (Django Admin + poweradmin) e endpoints JSON
  consumidos por integrações externas.

Atores:

- **Usuário externo** (pesquisador sem conhecimento técnico): cria projetos e
  termos, acompanha a coleta e exporta resultados, tudo pelo admin customizado.
- **Superusuário/operador**: administra todos os projetos, interrompe processos,
  executa rotinas de manutenção.
- **Agendador** (cron/scheduler): dispara os management commands de coleta e
  processamento fora do ciclo web.
- **Integração externa** (ex.: coletor de Telegram/Datalake): consome e atualiza
  status via os endpoints `/api/*`.

## Glossary

- **Projeto / Monitoramento**: unidade central de pesquisa; agrupa termos, redes,
  idioma default e estatísticas.
- **Termo**: critério de busca dentro de um projeto (query + período + idioma +
  tipo de busca).
- **Processamento**: registro de uma execução de rotina (coleta, importação,
  backup, etc.) associada a um termo.
- **Agendamento**: captura especial pontual (mais recentes, mais relevantes,
  retweets, comentários) com janela/limite próprios.
- **Datalake**: diretório `data/` onde os tweets são gravados como JSON antes de
  serem importados para o banco.
- **TweetInput**: ligação entre um Tweet e o Termo/Processamento que o trouxe.

## Requirements

### Requisito 1 — Gestão de projetos de monitoramento

**User story:** Como pesquisador, quero criar e gerir projetos de monitoramento,
para organizar minhas coletas por tema e acompanhar seus totais.

#### Critérios de aceitação

1. QUANDO um usuário cria um Projeto sem informar grupo, O sistema DEVE atribuir
   o grupo a partir do eixo do projeto ou, na ausência deste, do primeiro grupo
   do usuário.
2. QUANDO um Projeto é criado, O sistema DEVE registrar o usuário autenticado
   como dono do projeto.
3. ENQUANTO o usuário não for superusuário, O sistema DEVE tornar os campos do
   projeto somente-leitura se o usuário não pertencer ao grupo do projeto.
4. QUANDO um Projeto inclui a rede Telegram (id 4) mas não tem lista de canais
   definida, O sistema DEVE exibir aviso de que a busca pelo Telegram não poderá
   ser realizada.
5. O sistema DEVE expor, no projeto, totais calculados (lidos, estimados,
   retweets, favoritos, usuários únicos) e os contadores de termos ativos e
   processados.
6. QUANDO o prefixo (Elastic Prefix) é informado, O sistema DEVE normalizá-lo
   para minúsculas, remover espaços e caracteres não permitidos, e rejeitar
   prefixos iniciados por dígito.
7. SE `OPENSEARCH_SERVERS` estiver configurado E o projeto tiver prefixo, ENTÃO
   O sistema DEVE registrar o índice no catálogo do OpenSearch ao salvar.

### Requisito 2 — Gestão de termos de busca

**User story:** Como pesquisador, quero definir termos de busca com período e
idioma, para delimitar o que será coletado em cada projeto.

#### Critérios de aceitação

1. QUANDO um Termo é salvo, O sistema DEVE normalizar as aspas da query
   (curvas e apóstrofos para aspas retas duplas).
2. QUANDO um novo Termo é adicionado, O sistema DEVE registrar a ação no log do
   admin (LogEntry).
3. O sistema DEVE permitir configurar por termo: query, busca complementar,
   período (início/fim), idioma, inclusão de retweets e tipo de busca.
4. O sistema DEVE manter por termo os ponteiros de continuidade `prim_tweet`,
   `ult_tweet` e `ult_processamento` usados pelas estratégias de coleta.
5. QUANDO o operador aplica as ações de interromper, reativar ou finalizar
   termos, O sistema DEVE atualizar o status dos termos selecionados em lote.

### Requisito 3 — Coleta de tweets (crawler)

**User story:** Como operador, quero que o sistema colete automaticamente os
tweets dos termos ativos, para popular a base sem intervenção manual.

#### Critérios de aceitação

1. QUANDO o comando `crawler` é executado sem argumentos, O sistema DEVE
   processar os termos com status Ativo ou Fila, de projetos ativos, tipo de
   busca Full/Premium e associados à rede Twitter/X, em ordem de último
   processamento.
2. QUANDO um termo está em coleta regular (status Ativo), O sistema DEVE usar a
   estratégia contínua a partir do `ult_tweet` (since_id); na primeira execução,
   DEVE usar a data inicial do termo.
3. QUANDO um termo está em recuperação (status Fila/Interrompido), O sistema DEVE
   executar a estratégia de correção buscando registros entre o último
   capturado e o primeiro tweet do intervalo.
4. SE o tipo de busca não for Full E a última coleta ultrapassar 7 dias, ENTÃO
   O sistema DEVE limitar a data inicial à janela de 7 dias da API.
5. QUANDO o total coletado atingir o limite, O sistema DEVE marcar o termo como
   Fila e agendar um processamento contínuo a partir do menor tweet obtido.
6. QUANDO a coleta atinge a data final ou inicial programada do termo, O sistema
   DEVE marcar o termo como Concluído.
7. QUANDO cada tweet é obtido, O sistema DEVE gravá-lo como JSON no datalake
   (`data/` e `data/queue/`) por meio de `save_result`, reidratando os dados do
   autor a partir dos `includes`.
8. QUANDO ocorre falha de rede/servidor do Twitter, O sistema DEVE marcar o termo
   como Interrompido (não como Erro) e agendar continuação; QUANDO ocorre erro
   não relacionado ao Twitter, DEVE marcar como Erro.
9. QUANDO um termo fica com status Processando há mais de 1 hora, O sistema DEVE
   reativá-lo ao final da execução do crawler.
10. QUANDO o comando é chamado com `--fake`, O sistema DEVE simular sem alterar
    status nem registrar logs definitivos.
11. QUANDO o comando recebe `--twit`, O sistema DEVE coletar um único tweet por
    ID e gravá-lo como JSON.

### Requisito 4 — Agendamentos especiais

**User story:** Como operador, quero agendar capturas pontuais (mais recentes,
mais relevantes, retweets, comentários), para complementar a coleta regular.

#### Critérios de aceitação

1. QUANDO o `crawler` processa um Agendamento, O sistema DEVE usar a janela
   (datas ou since/until) definida no agendamento.
2. QUANDO o agendamento define ordenação por relevância, O sistema DEVE solicitar
   `sort_order=relevancy` à API.
3. QUANDO o agendamento conclui, O sistema DEVE registrar o intervalo capturado
   (`since_id`, `until_id`, `dt_corte`) e marcar o status como Concluído.
4. SE houver falha do Twitter, ENTÃO O sistema DEVE retornar o agendamento ao
   status Agendado para nova tentativa.

### Requisito 5 — Importação de dados coletados

**User story:** Como operador, quero importar para o banco os tweets coletados,
para que apareçam na interface e nas estatísticas.

#### Critérios de aceitação

1. QUANDO o comando `importjson data` é executado, O sistema DEVE varrer os JSON
   de `data/`, carregá-los no banco e remover os arquivos processados.
2. QUANDO já existe uma importação em andamento, O sistema DEVE abortar, exceto
   se `--force` for informado.
3. QUANDO um tweet é importado, O sistema DEVE criar/atualizar o `TweetUser`, o
   `Tweet`, seus retweets/quotes/replies (`Retweet`) e a ligação `TweetInput`
   com o termo e o processamento.
4. QUANDO o tweet referenciar outros (retweet/quote/reply), O sistema DEVE criar
   as referências `Retweet` e associar o tweet pai quando houver dados.
5. SE a data do tweet estiver fora do período do termo OU o idioma divergir do
   idioma do termo, ENTÃO O sistema NÃO DEVE associar o tweet ao termo.
6. QUANDO a importação termina, O sistema DEVE atualizar `last_count` de cada
   termo e o total do projeto, e registrar os totais no log.
7. QUANDO um arquivo JSON está corrompido, O sistema DEVE movê-lo para
   `data/ruim/` e interromper após 10 erros.
8. QUANDO o usuário importa um arquivo XLSX pela interface, O sistema DEVE
   converter cada linha para o formato esperado e importar os tweets.
9. QUANDO o usuário importa uma lista de IDs (arquivo .txt), O sistema DEVE
   agendar a reidratação desses tweets via API em thread de segundo plano.

### Requisito 6 — Busca na base local

**User story:** Como pesquisador, quero buscar nos tweets já coletados, para
reaproveitar a base sem novas chamadas à API.

#### Critérios de aceitação

1. QUANDO o usuário solicita busca local em um termo do tipo Busca Global ou
   Filtro no Projeto, O sistema DEVE executar a busca em thread de segundo plano.
2. SE o termo não for do tipo de busca local, ENTÃO O sistema DEVE recusar a
   operação com mensagem de erro.
3. QUANDO a busca local roda, O sistema DEVE aplicar os termos (incluindo
   exclusões com prefixo `-`) sobre o texto dos tweets e associar os que casam
   ao termo via `TweetInput`.
4. QUANDO a busca local conclui, O sistema DEVE marcar o termo como Concluído.

### Requisito 7 — Exportação e visualizações

**User story:** Como pesquisador, quero exportar os dados e ver visualizações,
para analisar o resultado da coleta.

#### Critérios de aceitação

1. QUANDO o usuário solicita o CSV, O sistema DEVE gerar em segundo plano os
   arquivos de tags e completo (zipados) e registrar um Processamento de tags.
2. QUANDO o usuário abre as estatísticas, O sistema DEVE exibir top tweets,
   gráfico de tweets por dia e disponibilizar o CSV de usuários.
3. QUANDO o usuário solicita a nuvem de palavras, O sistema DEVE gerar a imagem a
   partir das palavras mais comuns, respeitando as stopwords globais e do projeto.
4. QUANDO o usuário solicita o grafo, O sistema DEVE gerar o arquivo GEXF da rede
   de usuários (limitado aos 200 tweets com mais retweets).
5. QUANDO o usuário solicita o CSV Gephi, O sistema DEVE retornar o CSV de
   arestas (source/target) da rede de retweets.
6. QUANDO o usuário acessa o status de coleta de um termo, O sistema DEVE exibir
   o gráfico de tweets por dia a partir do OpenSearch (se configurado) ou do
   banco local.

### Requisito 8 — Backup e manutenção

**User story:** Como operador, quero fazer backup dos JSON e manter a base, para
preservar e limpar os dados coletados.

#### Critérios de aceitação

1. QUANDO o usuário solicita backup de um projeto, O sistema DEVE agendar um
   Processamento de backup; o `scheduler` DEVE executá-lo exportando para o S3.
2. QUANDO o usuário solicita excluir os JSON de um projeto, O sistema DEVE
   permitir a exclusão somente se houver backup concluído.
3. O sistema DEVE oferecer rotinas de manutenção: enriquecimento (geo, idioma,
   dados de usuário), remoção de JSON, remoção de não relacionados, reviver
   termos travados, verificação de integridade e correção de índices do
   OpenSearch.

### Requisito 9 — API JSON para integrações

**User story:** Como integração externa, quero consultar redes, projetos e termos
e atualizar o status de processamento, para coordenar a coleta de outras redes.

#### Critérios de aceitação

1. QUANDO uma requisição é feita aos endpoints protegidos, O sistema DEVE validar
   o cabeçalho `auth` contra `settings.AUTH_KEYS` e retornar 403 se inválido.
2. QUANDO a rede consultada é Telegram (id 4), O sistema DEVE retornar a lista de
   canais ativos associados ao projeto, com o status da coleta por termo/rede.
3. QUANDO a integração atualiza o status de um termo/rede, O sistema DEVE gravar
   o `ult_processo` (ou status de erro) em `TermoStatus`.

## Pontos de atenção (dívidas técnicas e riscos)

> Levantados a partir da leitura do código atual. São candidatos a melhorias, não
> comportamento desejado documentado.

1. **SQL dependente de MySQL em `views.py` / `models.py`.** Várias consultas usam
   `DATE_FORMAT`/`ifnull` (MySQL) em SQL cru. Isso quebra se o `default` apontar
   para outro banco e dificulta testes. *Sugestão:* mover para o ORM ou isolar
   em uma camada de repositório por dialeto.
2. **Endpoint `processo_rede_set` com `@csrf_exempt` e sem auth.** A verificação
   de `AUTH_KEYS` está comentada, deixando um endpoint de escrita aberto.
   *Sugestão:* reativar a autenticação antes de qualquer uso em produção.
3. **`rede_id == 4` e `nome='Twitter/X'` hardcoded.** O id do Telegram e o nome da
   rede estão fixos no código (`api.py`, `crawler.py`). *Sugestão:* referenciar
   por slug/choice ou configuração.
4. **Threads via `threading.Thread` para tarefas longas** (busca local, geração
   de CSV, reidratação de lista). Sem controle de concorrência, retentativa ou
   visibilidade de falha; morrem com o processo web. *Sugestão:* migrar para fila
   de tarefas (Celery/RQ) ou management command agendado.
5. **`scheduler.py` só trata backup.** O docstring/roadmap sugere orquestração
   ampla, mas hoje o comando executa apenas `PROC_BACKUP`. *Sugestão:* documentar
   claramente ou completar a orquestração.
6. **`core/client.py` é uma cópia vendorizada do `Client` do tweepy.** Mais de
   3 mil linhas copiadas da biblioteca, fora do controle de versão do upstream.
   *Sugestão:* se houver customização, isolá-la em subclasse; senão, usar o
   tweepy diretamente.
7. ~~**`index`/`visao` incompletas.** `visao(request)` retorna `None` (gera erro
   500) e `ProjetoAdmin.visao` chama `render` sem `request` como 1º argumento.~~
   **(Resolvido)** `ProjetoAdmin.visao` passou a usar `render(request, template,
   context)` e a rota pública `^visao/$` (placeholder que retornava `None`) foi
   removida junto com a função `views.visao`. A funcionalidade real segue no
   admin (`admin:core_projeto_visao`).
8. **Blocos grandes comentados** em `views.py` (heatmap), `crawler.py` e
   `admin.py`. *Sugestão:* remover ou converter em feature flag documentada.
9. ~~**`finalizar_projeto_action` chama `termo.tot_twits()`** como se fosse método,
   mas `tot_twits` é `@property` — potencial `TypeError`.~~ **(Resolvido)** A
   chamada foi corrigida para `termo.tot_twits` (sem parênteses).
10. **Idiomas de `Termo.language` (2 chars) vs `Tweet.language` (5 chars).** A
    comparação direta de idioma na importação pode falhar para variantes
    regionais. *Sugestão:* normalizar antes de comparar.
11. **`nuvem` monta caminho com `os.path.join(path, filename)` já absoluto**,
    podendo gerar caminho incorreto. *Sugestão:* revisar a construção do path.
12. **Ausência de testes automatizados na `core`** (`core/tests.py` praticamente
    vazio). *Sugestão:* cobrir ao menos `importjson.load_twitter` e as
    estratégias do crawler com `SimpleTestCase`/mocks.
