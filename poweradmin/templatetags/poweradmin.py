# coding: utf-8
from django.template import Library
from datetime import datetime

register = Library()


@register.filter(name='strptime')
def strptime(value, mash):
    return datetime.strptime(value, mash)


@register.inclusion_tag('admin/date_hierarchy.html', takes_context=True)
def power_date_hierarchy(context, cl):
    """
    Displays the date hierarchy for date drill-down functionality.
    """
    if cl.date_hierarchy:
        request = context.get('request')
        field_name = cl.date_hierarchy
        field = cl.opts.get_field(field_name)

        value__gte = value__lte = None
        if request.GET.get('%s__gte' % field_name):
            value__gte = datetime.strptime(request.GET.get('%s__gte' % field_name), "%Y-%m-%d")
        if request.GET.get('%s__lte' % field_name):
            value__lte = datetime.strptime(request.GET.get('%s__lte' % field_name), "%Y-%m-%d")

        return {
            'show': True,
            'field_name__gte': u'%s__gte' % field_name,
            'field_name__lte': u'%s__lte' % field_name,
            'field': field,
            'value__gte': value__gte,
            'value__lte': value__lte,
            'request': request,
        }