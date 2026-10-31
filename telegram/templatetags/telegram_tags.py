import re

from django import template
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def milhar(valor):
    # separador de milhar pt-BR (ponto), independente das settings
    try:
        return f'{int(valor):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return '0'


@register.filter
def destaca(texto, termo):
    # casa no texto original e escapa cada pedaço, para o termo não quebrar entidades HTML (ex.: "amp")
    texto = str(texto or '')
    termo = (termo or '').strip()
    if not termo:
        return conditional_escape(texto)
    partes = re.split('(' + re.escape(termo) + ')', texto, flags=re.IGNORECASE)
    # com um único grupo de captura, os índices ímpares são as ocorrências do termo
    html = ''.join(f'<mark>{escape(p)}</mark>' if i % 2 else escape(p) for i, p in enumerate(partes))
    return mark_safe(html)
