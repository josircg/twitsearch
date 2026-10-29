# Requisitos — Painel de projetos (issue 36)

## Introdução
View `/painel/` que lista os projetos do usuário logado, com atalhos para criar novas coletas.

## Requisitos

### 1. Acesso restrito
**User story:** Como usuário, quero acessar meu painel apenas autenticado, para que meus projetos não fiquem expostos.

Critérios de aceite:
1. WHEN um usuário não autenticado acessa `/painel/` THEN o sistema SHALL redirecioná-lo para o login (`/admin/login/`).
2. WHEN um usuário autenticado acessa `/painel/` THEN o sistema SHALL exibir a página com status 200.

### 2. Cabeçalho
**User story:** Como usuário, quero ver o mesmo cabeçalho da home, para ter navegação consistente.

Critérios de aceite:
1. O template SHALL estender `base.html`, mantendo cabeçalho e rodapé da home.

### 3. Botões de ação
**User story:** Como usuário, quero atalhos para iniciar novas coletas.

Critérios de aceite:
1. O painel SHALL exibir os botões "Nova coleta Telegram" e "Nova coleta Youtube".
2. WHEN o usuário é `is_staff` THEN o botão "Admin" SHALL estar habilitado e apontar para `/admin/`.
3. WHEN o usuário não é `is_staff` THEN o botão "Admin" SHALL aparecer desabilitado.

### 4. Lista de projetos
**User story:** Como usuário, quero ver meus projetos e seu status.

Critérios de aceite:
1. O painel SHALL listar apenas projetos cujo `usuario` seja o usuário logado, ordenados por nome.
2. Cada item SHALL mostrar Nome e Status (`get_status_display`).
3. WHEN o usuário não possui projetos THEN o painel SHALL exibir "Nenhum projeto registrado".

## Fora de escopo
- Tela de coleta do Youtube (o botão aponta para `#` até existir).
- Links de detalhe/estatística por projeto.
