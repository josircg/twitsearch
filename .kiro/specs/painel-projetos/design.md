# Design — Painel de projetos

## Visão geral
View baseada em função, protegida por `login_required`, renderizando um template que estende `base.html`.

## Componentes
| Arquivo | Alteração |
|---|---|
| `core/views.py` | Nova view `painel(request)`; consulta `Projeto.objects.filter(usuario=request.user).order_by('nome')` |
| `core/urls.py` | `path('painel/', painel, name='painel')` |
| `templates/painel.html` | Botões, tabela Nome/Status e mensagem de lista vazia |

## Decisões
- `login_url='/admin/login/'` porque o projeto não define `LOGIN_URL`.
- Botão Telegram aponta para `importacao_canais` (única tela de Telegram existente); Youtube é placeholder (`#`).
- Botão Admin é desabilitado (não oculto) para não-staff.

## Modelo de dados
Usa `core.models.Projeto` (`nome`, `status` com choices A/I/C, `usuario` FK). Sem migrações.

## Testes
- Anônimo → 302 para o login.
- Usuário comum vê só os próprios projetos; staff vê botão Admin habilitado.
- Sem projetos → mensagem "Nenhum projeto registrado".
