# coding: utf-8
from django import template

from django.conf import settings
import re

register = template.Library()


@register.simple_tag
def site_name():
    return settings.SITE_NAME


@register.simple_tag
def version():
    return settings.VERSION


@register.tag(name='cleanwhitespace')
def do_cleanwhitespace(parser, token):
    nodelist = parser.parse(('endcleanwhitespace',))
    parser.delete_first_token()
    return CleanWhitespaceNode(nodelist)


class CleanWhitespaceNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        output = re.sub(r'\n[\s\t]*(?=\n)', '', output)
        output = re.sub(r'[\s\t]{2,}', '', output)
        output = output.strip()
        return output
