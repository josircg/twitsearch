# Requirements Document

_App `utils` do Capitu._

> **Natureza deste documento.** Documentação de **engenharia reversa** do
> comportamento atual da app `utils`. Descreve o que o sistema faz hoje, para
> servir de referência de manutenção. Pontos de atenção estão ao final.

## Introduction

A app `utils` é uma app de apoio, sem modelos próprios. Ela cumpre dois papéis
transversais no Capitu:

1. **Visibilidade de auditoria**: registra o modelo `LogEntry` do Django
   (`django.contrib.admin.models`) no admin, dando aos operadores uma tela de
   consulta ao histórico de ações — que o resto do sistema alimenta via
   `log_message`/`alog_message` da `core`.
2. **Envio de e-mail**: oferece funções utilitárias para disparo de e-mail
   (simples e via template) de forma assíncrona, reutilizáveis por qualquer app.

A app não tem URLs, views, forms nem management commands próprios. Seu
`UtilsConfig` apenas registra a app; o admin e as funções de e-mail são o
conteúdo efetivo.

## Glossary

- **LogEntry**: modelo nativo do Django que registra ações no admin (adição,
  alteração, exclusão). No Capitu também é usado como log de aplicação, gravado
  por `core.log_message` e `core.apps.alog_message`.
- **Helper de e-mail**: função utilitária que encapsula o envio de e-mail do
  Django, executado em thread para não bloquear a resposta.

## Requirements

### Requisito 1 — Consulta ao histórico de ações (LogEntry)

**User story:** Como operador, quero consultar no admin o histórico de ações do
sistema, para auditar o que foi feito e por quem.

#### Critérios de aceitação

1. O sistema DEVE registrar o modelo `LogEntry` no admin, em modo somente-leitura.
2. O sistema DEVE listar data/hora, usuário, tipo de conteúdo, tipo da ação,
   representação do objeto e a mensagem de alteração.
3. O sistema DEVE permitir filtrar por data, tipo de conteúdo e tipo de ação.
4. O sistema DEVE oferecer busca múltipla por representação do objeto, mensagem e
   usuário.
5. QUANDO uma linha é exibida, O sistema DEVE traduzir o tipo da ação para um
   rótulo legível (Adicionado / Modificado / Deletado).

### Requisito 2 — Envio de e-mail assíncrono

**User story:** Como desenvolvedor, quero funções reutilizáveis para enviar
e-mail sem bloquear a requisição, para notificar eventos do sistema.

#### Critérios de aceitação

1. O sistema DEVE oferecer o envio de e-mail a partir de um template Django
   (`send_templated_email`) e de um texto simples (`send_message_email`).
2. QUANDO o remetente não é informado, O sistema DEVE usar
   `settings.DEFAULT_FROM_EMAIL`.
3. O sistema DEVE permitir anexos como tuplas `(filename, content, mimetype)`.
4. O sistema DEVE executar o envio em thread separada, para não bloquear o fluxo
   chamador.
5. O sistema DEVE enviar o conteúdo também como alternativa `text/html`.

## Pontos de atenção (dívidas técnicas e riscos)

1. ~~**Envio de e-mail em `Thread` sem tratamento de erro.** Uma falha de SMTP na
   thread é silenciosa (sem log nem retentativa) e não chega ao chamador.~~
   **(Resolvido)** O envio foi centralizado em `_send_async`, que captura
   exceções e registra com `logger.exception`. (Uma fila de tarefas para
   retentativa/volume continua sendo uma melhoria futura.)
2. ~~**Código de envio duplicado** entre `send_templated_email` e
   `send_message_email`.~~ **(Resolvido)** A lógica comum (remetente default,
   alternativa HTML, anexos, erro e thread) foi extraída para `_send_async`; as
   funções públicas apenas determinam o corpo HTML e delegam.
3. **`send_message_email` trata o corpo como `text/html`.** O corpo é registrado
   como alternativa HTML (comportamento assumido pelo uso atual, que monta o
   texto com `<br>`). *Documentado* no docstring; manter como HTML por
   compatibilidade.
4. **`send_templated_email` sem uso atual.** Só `send_message_email` é chamado
   (em `core/.../verifica_integridade.py`). *Sugestão:* manter se houver uso
   previsto; caso contrário, remover para reduzir superfície.
5. **Ausência de testes** (`utils` não tem `tests.py`). *Sugestão:* testar os
   helpers de e-mail com o backend `locmem` do Django.
