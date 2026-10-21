# Design Document

_App `utils` do Capitu._

> **Natureza deste documento.** Documentação de **engenharia reversa** do design
> atual da app `utils`. Não é a proposta de uma feature nova.

## Overview

A `utils` é uma app Django mínima, sem modelos, URLs ou views. Concentra duas
utilidades transversais: o registro do `LogEntry` nativo no admin (tela de
auditoria) e um par de funções de envio de e-mail assíncrono. Serve o resto do
sistema — em especial a `core`, que grava `LogEntry` via `log_message` e dispara
e-mail de integridade via `send_message_email`.

A escolha de design é deliberadamente leve: nenhuma persistência própria, apenas
configuração de admin e funções puras de infraestrutura.

## Architecture

```
  Qualquer app (core, telegram)
        │  log_message / alog_message
        ▼
   django LogEntry  ──(registro no admin)──►  utils.admin.LogEntryAdmin  ──► Operador

  core/verifica_integridade  ──► utils.email.send_message_email ──(Thread)──► SMTP (Django mail)
```

A `utils` não inicia fluxos; é sempre invocada por outras apps. Não possui
`AppConfig` além do `UtilsConfig` padrão e está declarada em `INSTALLED_APPS`
para que o `admin.py` seja carregado.

## Components and Interfaces

### 1. `utils/admin.py` — `LogEntryAdmin`

Registra `django.contrib.admin.models.LogEntry` com `PowerModelAdmin`:

- `list_display`/`fields`/`readonly_fields`: data, usuário, tipo de conteúdo,
  tipo da ação derivado, objeto e mensagem — tudo somente leitura.
- `list_filter`: por `action_time`, `content_type`, `action_flag`.
- `multi_search`: por representação do objeto, mensagem e usuário.
- `tipo(obj)`: método de exibição que traduz `is_addition/is_change/is_deletion`
  para rótulos legíveis.

### 2. `utils/email.py` — helpers de e-mail

- `_send_async(subject, html_content, recipient_list, from_email=None,
  attachments=None)` (privada): centraliza o envio comum — remetente default,
  `EmailMultiAlternatives` com alternativa HTML, anexos, captura de erro com
  `logger.exception` e disparo em `threading.Thread`.
- `send_templated_email(...)`: renderiza um template (`render_to_string`, no
  chamador) e delega a `_send_async`.
- `send_message_email(...)`: passa o corpo (tratado como HTML) direto a
  `_send_async`.

Todas usam `settings.DEFAULT_FROM_EMAIL` como remetente default e suportam anexos
`(filename, content, mimetype)`.

### 3. `utils/apps.py` — `UtilsConfig`

AppConfig padrão; apenas nomeia a app.

## Data Models

A app **não define modelos**. Opera sobre o modelo nativo
`django.contrib.admin.models.LogEntry`, apenas registrando-o no admin.

| Entidade        | Origem            | Papel na `utils` |
|-----------------|-------------------|------------------|
| `LogEntry`      | `django.contrib.admin` | Exibido em modo somente-leitura (auditoria). |

## Correctness Properties

1. **Auditoria somente-leitura.** Nenhum campo do `LogEntry` é editável pelo
   admin da `utils`, preservando a integridade do histórico.
2. **Não bloqueio do chamador.** O envio de e-mail retorna imediatamente; o
   trabalho de rede ocorre na thread.
3. **Remetente determinístico.** Na ausência de `from_email`, o remetente é
   sempre `settings.DEFAULT_FROM_EMAIL`.

## Error Handling

- **Admin.** Sem escrita; não há caminhos de erro de validação próprios.
- **E-mail.** O envio roda em `Thread`; `_send_async` captura exceções e as
  registra com `logger.exception` (não há retentativa). A renderização de
  template em `send_templated_email` ocorre no chamador, de modo que um template
  inexistente falha de imediato em vez de se perder na thread. O chamador não
  recebe retorno de sucesso/erro (envio fire-and-forget).

## Testing Strategy

> Estado atual: sem testes. Estratégia recomendada.

- **E-mail (`locmem` backend).** Configurar
  `EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'` em teste e
  verificar `mail.outbox` para assunto, remetente default, destinatários, anexos
  e alternativa HTML. Como o envio é em thread, o teste deve sincronizar (join) ou
  isolar o `_sendmail` para chamada direta.
- **Admin.** Teste leve garantindo que `LogEntry` está registrado e é
  somente-leitura, e que `tipo` mapeia corretamente os três `action_flag`.

## Pontos de atenção (design)

1. ~~**Falhas de e-mail silenciosas** na thread — sem log.~~ **(Resolvido)**
   `_send_async` registra exceções com `logger.exception`. Retentativa ainda não
   existe.
2. ~~**Código de envio duplicado** entre as duas funções.~~ **(Resolvido)**
   Unificado em `_send_async`.
3. **Thread por envio** não escala para volume; uma fila de tarefas seria mais
   robusta se o uso crescer.
4. **`send_message_email` trata o corpo como HTML** — documentado; mantido por
   compatibilidade com o uso atual.
5. **Função `send_templated_email` sem consumidor atual.**
