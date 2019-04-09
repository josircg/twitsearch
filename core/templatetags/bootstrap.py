# coding:utf-8
from django import template
from django.utils.html import mark_safe

register = template.Library()

@register.filter(name='btform')
def btform(field):
    html = u'%s' % field
    if '<select id' in html:
        html = html.replace('<select id','<div class ="select is-fullwidth"><select id')
        html = html.replace('</select>','</select></div>')
    elif '<textarea' in html:
        html = html.replace('name=', 'class="textarea" name=')
    elif ('type="radio"' not in html) and ('type="checkbox"' not in html):
        html = html.replace('name=', 'class="input" name=')
    if field.help_text:
        html = html.replace('name=', ' placeholder="%s" name=' % field.help_text)
    if field.errors:
        html = html.replace('class="input"', 'class="input is-danger"').replace('class="textarea"', 'class="textarea is-danger"')
    return mark_safe(html)

@register.filter(name='btischeckbox')
def btischeckbox(field):
    return 'type="checkbox"' in str(field)

@register.filter(name='btisradio')
def btisradio(field):
    if 'type="radio"' in str(field):
        return True
    return False