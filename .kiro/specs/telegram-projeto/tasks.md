# Tarefas — Registro de projeto de coleta Telegram

- [x] 1. Adicionar `Projeto.url_resumo` em `core/models.py` (req. 4.5)
- [x] 2. Criar `TelegramProjectForm` em `telegram/forms.py` com validação de datas e termos (req. 2, 3)
- [x] 3. Criar view `telegram_project` com `login_required`, queryset de listas por usuário e gravação atômica (req. 1, 4)
- [x] 4. Registrar rota `telegram/projetos/novo/` em `core/urls.py` (req. 1)
- [x] 5. Criar `templates/telegram_project.html` com instruções AND/OR e botão de importar lista (req. 2.3, 2.5)
- [x] 6. Atualizar `templates/painel.html`: link do botão Telegram e exibição de `messages` (req. 5)
- [x] 7. Escrever testes em `telegram/tests.py` conforme o design
- [x] 8. Verificação manual no navegador
- [x] 9. Importar lista (req. 6): módulo `telegram/importacao.py`, `ImportListaForm`, view, rota, template e botão
- [x] 10. Testes da importação de lista

## Pendências (fora desta entrega — ver "Pendências" em requirements.md)
- [ ] P1. Aplicar termos (AND/OR) e período na coleta e no export do Telegram
- [x] P2. Importação da própria lista integrada ao formulário (tarefa 9)
- [ ] P5. Unificar `importacao_canais` (admin) com `telegram/importacao.py`
- [ ] P3. Remover o id `4` hardcoded da rede Telegram no admin de `TermoStatus`
- [x] P4. Padronizar prefixo das rotas do app telegram (feito em `telegram-lista-canais`, req. 10)
