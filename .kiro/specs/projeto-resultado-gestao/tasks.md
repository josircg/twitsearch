# Tarefas — Resultado do projeto no Gestão (acesso por hash)

A parte do Gestão também está descrita na spec do próprio repositório: `gestao-minerva/.spec/projeto-resultado-gestao/`.

## 0. Antes de começar
- [x] 0.1 Decisões confirmadas (requirements.md, "Decisões"): ambiente único, escrita e exportação bloqueadas, `ds` fixo `telegram` sem usar o prefixo
- [ ] 0.2 Confirmar com quem mantém o pipeline que `monitoramento_id = Projeto.id` e `monitoramento_nome = Projeto.nome`, e que existe em cada ambiente do Gestão um `DataSource` `telegram` apontando para o índice dos documentos do Telegram (Pendência 3)
- [ ] 0.3 Gerar `PROJETO_HASH_KEY` e configurá-la no Capitu e em cada ambiente do Gestão que aceitar o link; definir `GESTAO_URL` no Capitu

## Capitu (`twitsearch`)
- [x] 1. Criar a constante `DS_TELEGRAM = 'telegram'` e usá-la no link, sem ler `Projeto.prefix` (req. 3.1, 3.2)
- [x] 2. Tirar a gravação de `prefix` do `telegram_project`; link só para projetos com a rede Telegram (req. 3.3, 3.5)
- [x] 3. Criar `core/hash_projeto.py` com `hash_projeto(id, ds)` e `token_projeto(id, ds)` (req. 1)
- [x] 4. Adicionar `Projeto.url_resultado` em `core/models.py` (req. 2.1, 2.2)
- [x] 5. Adicionar a coluna "Resultado" em `templates/painel.html`, com `mostrar_resultado` na view `painel` (req. 2.3–2.5)
- [x] 6. (Opcional) Adicionar o link em `ProjetoAdmin.list_display` (req. 2.6)
- [x] 7. Documentar `GESTAO_URL` e `PROJETO_HASH_KEY` em `doc/local.py`
- [x] 8. Escrever os testes do Capitu conforme o design

## Gestão (`gestao-minerva`)
- [x] 9. Criar `utils/hash_projeto.py` com `valida_hash(token, ds)` (req. 4, 11)
- [x] 10. Sessão: criar `get/set/limpa_projeto_acesso` e adaptar `set_opensearch_index` ao modo projeto (req. 5, 9.2)
- [x] 11. Dispensar a checagem de grupo em `_get_opensearch_connection` só para o `ds` da entrada e devolver `ClienteProjeto` (req. 5.3, 6.5)
- [x] 12. Auditar todos os construtores chamados por `filter_dashboard`, `list_result_data` e `get_alerts` e as chamadas diretas ao client em `views.py`, para confirmar que passam pelo invólucro (req. 6.5, 6.6)
- [x] 13. Criar os decorators `login_or_projeto_required` (com a entrada por `?hash=&ds=` e o redirecionamento) e `bloqueado_no_projeto`, e aplicá-los conforme a tabela do design (req. 4, 7)
- [x] 14. Aplicar `aplica_filtro_projeto` em `dashboards`, `list_results_view` e `alerts_view`, com o título vindo de `monitoramento_nome` (req. 6.2, 6.8)
- [x] 15. Bloquear a exportação no modo projeto: ocultar "Baixar csv" e responder 403 ao POST `export` (req. 8)
- [x] 16. Checar o dono do registro em `record_view` e `visualization`, e recusar POST de arquivar/tag (req. 7.2, 7.5)
- [x] 17. Ajustar os templates: título do projeto, sem seletor de assunto, "Limpar", feedback de IA e ações do dataset; navbar (req. 7.5–7.7)
- [x] 18. Escrever os testes do Gestão conforme o design, com atenção aos de entrada (`ds` trocado) e de persistência na sessão
- [ ] 19. Verificação manual: criar um projeto Telegram → "Ver resultado" no painel → dashboard → paginar o dataset → filtros → alertas → registro; conferir que não há "Baixar csv"; tentar trocar `ds`, `monitoramento_id` e o id do hash

## Pendências (fora desta entrega — ver requirements.md)
- [ ] P1. Associar as mensagens do Telegram a termos e projetos (P1 de `telegram-projeto`); sem isso, o resultado dos projetos Telegram fica vazio
- [ ] P2. Rever os `monitoramento_id` fixos (`86`, `19`) no fluxo normal do Gestão
- [ ] P3. `DataSource` `telegram` em cada ambiente do Gestão (tarefa 0.2)
- [ ] P4. Revogar o link por projeto (Decisões, item 4)
