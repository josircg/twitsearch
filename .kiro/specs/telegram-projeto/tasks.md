# Tarefas — Registro de projeto de coleta Telegram

- [x] 1. Adicionar `Projeto.url_resumo` em `core/models.py` (req. 4.5)
- [x] 2. Criar `TelegramProjectForm` em `telegram/forms.py` com validação de datas e termos (req. 2, 3)
- [x] 3. Criar view `telegram_project` com `login_required`, queryset de listas por usuário e gravação atômica (req. 1, 4)
- [x] 4. Registrar rota `telegram_project/` em `core/urls.py` (req. 1)
- [x] 5. Criar `templates/telegram_project.html` com instruções AND/OR e botão de importar lista (req. 2.3, 2.5)
- [x] 6. Atualizar `templates/painel.html`: link do botão Telegram e exibição de `messages` (req. 5)
- [x] 7. Escrever testes em `telegram/tests.py` conforme o design
- [x] 8. Verificação manual no navegador

## Pendências (fora desta entrega — ver "Pendências" em requirements.md)
- [ ] P1. Aplicar termos (AND/OR) e período na coleta e no export do Telegram
- [ ] P2. Importação da própria lista integrada ao formulário (cria lista privada e retorna ao formulário)
- [ ] P3. Remover o id `4` hardcoded da rede Telegram no admin de `TermoStatus`
- [ ] P4. Padronizar prefixo das rotas do app telegram
