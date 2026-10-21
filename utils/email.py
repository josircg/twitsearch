import logging

from threading import Thread
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


def _send_async(subject, html_content, recipient_list, from_email=None, attachments=None):
    """
    Dispara, em uma thread separada, o envio de um e-mail HTML.

    Centraliza a lógica comum de envio (remetente default, alternativa HTML,
    anexos e tratamento de erro) usada pelas funções públicas deste módulo.

    Args:
        subject (str): Assunto do email.
        html_content (str): Corpo do email (HTML).
        recipient_list (list): Lista de emails de destino.
        from_email (str, opcional): Email do remetente. Usa settings.DEFAULT_FROM_EMAIL se não informado.
        attachments (list, opcional): Lista de tuplas (filename, content, mimetype).
    """
    def _sendmail():
        try:
            remetente = from_email or settings.DEFAULT_FROM_EMAIL
            msg = EmailMultiAlternatives(subject, html_content, remetente, recipient_list)
            msg.attach_alternative(html_content, "text/html")
            if attachments:
                for attachment in attachments:
                    msg.attach(*attachment)
            msg.send()
        except Exception:
            logger.exception('Falha ao enviar e-mail para %s', recipient_list)

    Thread(target=_sendmail).start()


def send_templated_email(subject, template_name, context, recipient_list, from_email=None, attachments=None):
    """
    Envia um email usando um template Django.

    Args:
        subject (str): Assunto do email.
        template_name (str): Caminho do template (ex: 'emails/welcome.html').
        context (dict): Contexto para renderizar o template.
        recipient_list (list): Lista de emails de destino.
        from_email (str, opcional): Email do remetente. Usa settings.DEFAULT_FROM_EMAIL se não informado.
        attachments (list, opcional): Lista de tuplas (filename, content, mimetype).
    """
    html_content = render_to_string(template_name, context)
    _send_async(subject, html_content, recipient_list, from_email, attachments)


def send_message_email(subject, message, recipient_list, from_email=None, attachments=None):
    """
    Envia um email simples (sem template). O corpo é tratado como HTML.

    Args:
        subject (str): Assunto do email.
        message (str): Corpo do email (HTML).
        recipient_list (list): Lista de emails de destino.
        from_email (str, opcional): Email do remetente. Usa settings.DEFAULT_FROM_EMAIL se não informado.
        attachments (list, opcional): Lista de tuplas (filename, content, mimetype).
    """
    _send_async(subject, message, recipient_list, from_email, attachments)
