from threading import Thread
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


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
    def _sendmail(subject, template_name, context, recipient_list, from_email, attachments):
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        html_content = render_to_string(template_name, context)
        msg = EmailMultiAlternatives(subject, html_content, from_email, recipient_list)
        msg.attach_alternative(html_content, "text/html")
        if attachments:
            for attachment in attachments:
                msg.attach(*attachment)
        msg.send()

    thread = Thread(target=_sendmail, args=(subject, template_name, context, recipient_list, from_email, attachments))
    thread.start()
    
    
def send_message_email(subject, message, recipient_list, from_email=None, attachments=None):
    """
    Envia um email simples (sem template).

    Args:
        subject (str): Assunto do email.
        message (str): Corpo do email.
        recipient_list (list): Lista de emails de destino.
        from_email (str, opcional): Email do remetente. Usa settings.DEFAULT_FROM_EMAIL se não informado.
        attachments (list, opcional): Lista de tuplas (filename, content, mimetype).
    """
    def _sendmail(subject, message, recipient_list, from_email, attachments):
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        msg = EmailMultiAlternatives(subject, message, from_email, recipient_list)
        msg.attach_alternative(message, "text/html")
        if attachments:
            for attachment in attachments:
                msg.attach(*attachment)
        msg.send()

    thread = Thread(target=_sendmail, args=(subject, message, recipient_list, from_email, attachments))
    thread.start()


    