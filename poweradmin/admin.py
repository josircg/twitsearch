# -*- coding: utf-8 -*-
import operator
from .models import UserAdminConfig
from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.admin.utils import flatten_fieldsets
from django.conf import settings
from django.conf.urls import url
from django.urls import resolve
from django.http import HttpResponseRedirect, HttpResponse
from django import forms

import json

from django.contrib.auth import get_permission_codename

from .actions import export_as_csv_action, delete_selected, report_action


'''
 Features:
 - novo filtro multi_search
 - list_filter no cabeçalho da página ao invés de ficar na lateral

 multi_search sintaxe:
     multi_search = (
        ('q1', 'Nome', ['disciplina__nome']),
        ('q2', 'E-mail', ['email']),
    )
'''


POWERADMIN_USE_WIKI = getattr(settings, 'POWERADMIN_USE_WIKI', False)
POWERADMIN_WIKI_ARTICLE_URL = getattr(settings, 'POWERADMIN_WIKI_ARTICLE_URL', '/wiki/{path}/')


#Trim solution
class _BaseForm(object):
    def clean(self):
        for field in self.cleaned_data:
            # py2 and py3
            try:
               localbasestring = str
            except NameError:
                # Python 3
                localbasestring = str
            if isinstance(self.cleaned_data[field], localbasestring):
               self.cleaned_data[field] = self.cleaned_data[field].strip()

        return super(_BaseForm, self).clean()

class BaseModelForm(_BaseForm, forms.ModelForm):
    pass


class PowerModelAdmin(admin.ModelAdmin):
    buttons = []
    multi_search = []
    list_select_related = True
    multi_search_query = {}
    queryset_filter = {}
    form = BaseModelForm

    def has_change_permission(self, request, obj=None):
        change = get_permission_codename('change', self.opts) # Alterar
        view = get_permission_codename('view', self.opts) # Visualizar
        browser = get_permission_codename('browser', self.opts) # Visualizar listagem
        if obj:
            return request.user.has_perm("%s.%s" % (self.opts.app_label, change)) or request.user.has_perm("%s.%s" % (self.opts.app_label, view))
        return request.user.has_perm("%s.%s" % (self.opts.app_label, change)) or request.user.has_perm("%s.%s" % (self.opts.app_label, browser))

    def has_readonly_permission(self, request, obj=None):
        change = get_permission_codename('change', self.opts)
        view = get_permission_codename('view', self.opts)
        if not request.user.has_perm("%s.%s" % (self.opts.app_label, change)) and request.user.has_perm("%s.%s" % (self.opts.app_label, view)):
            return True
        return False

    def _all_fields(self, request, obj=None):
        if self.fields:
            return self.fields
        if self.fieldsets:
            return flatten_fieldsets(self.get_fieldsets(request, obj))
        fields = [field.name for field in self.opts.local_fields]
        if 'id' in fields: fields.remove('id')
        return fields

    def get_readonly_fields(self, request, obj=None):
        change_permission = super(PowerModelAdmin, self).has_change_permission(request, obj)
        view = get_permission_codename('view', self.opts)
        if not change_permission and request.user.has_perm("%s.%s" % (self.opts.app_label, view)):
            return self._all_fields(request, obj)
        return super(PowerModelAdmin, self).get_readonly_fields(request, obj)

    def get_list_display_links(self, request, list_display):
        change = get_permission_codename('change', self.opts)
        view = get_permission_codename('view', self.opts)
        browser = get_permission_codename('browser', self.opts)
        # Não coloca o link se não tiver permissões de editar ou visualizar
        if not (request.user.has_perm("%s.%s" % (self.opts.app_label, change)) or request.user.has_perm("%s.%s" % (self.opts.app_label, view))) and request.user.has_perm("%s.%s" % (self.opts.app_label, browser)):
            return []
        return super(PowerModelAdmin, self).get_list_display_links(request, list_display)

    def get_list_csv(self, request):
        if getattr(self, 'list_csv', None):
            return self.list_csv
        return self.get_list_display(request)

    def get_list_report(self, request):
        if getattr(self, 'list_report', None):
            return self.list_report
        return self.get_list_display(request)

    def get_header_report(self, request):
        if getattr(self, 'header_report', None):
            return self.header_report
        return u'<h1>Relatório de %s</h1>' % self.opts.model._meta.verbose_name_plural.capitalize()

    def get_actions(self, request):
        actions = super(PowerModelAdmin, self).get_actions(request)

        # Exportação do csv
        export_as_csv = export_as_csv_action(fields=self.get_list_csv(request))
        actions['export_as_csv'] = (export_as_csv, 'export_as_csv', export_as_csv.short_description)

        # Report
        report = report_action(fields=self.get_list_report(request), header=self.get_header_report(request))
        actions['report'] = (report, 'report', report.short_description)

        #Ajustes no log do action delete_selected
        actions['delete_selected'] = (delete_selected, 'delete_selected', delete_selected.short_description)
        return actions

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        #Verifica se a tela é readonly
        if self.has_readonly_permission(request, obj):
            readonly = True
        else:
            readonly = False
            fields = []
            for field in list(flatten_fieldsets(self.get_fieldsets(request, obj))):
                if isinstance(field, str):
                    fields.append(field)
                else:
                    fields += field

            readonly_fields = self.get_readonly_fields(request, obj)
            if set(fields) == set(readonly_fields).intersection(set(fields)):
                readonly = True

            for inline in context['inline_admin_formsets']:
                if set(flatten_fieldsets(inline.fieldsets)) != set(inline.readonly_fields).intersection(set(flatten_fieldsets(inline.fieldsets))):
                    readonly = False

        opts = self.model._meta
        app_label = opts.app_label

        object_id = obj.pk if obj else obj
        buttons = self.get_buttons(request, object_id)

        if POWERADMIN_USE_WIKI:
            path = '{0}-{1}'.format(app_label.lower(), opts.object_name.lower())
            from wiki.models import Article, ArticleRevision, URLPath
            from django.contrib.sites.shortcuts import get_current_site

            if not URLPath.objects.filter(slug=path).count():
                if not URLPath.objects.count():
                    URLPath.create_root(
                        site=get_current_site(request),
                        title=u'Root',
                        content=u"",
                        request=request
                    )
                root = URLPath.objects.order_by('id')[0]

                URLPath.create_article(
                    root,
                    path,
                    site=get_current_site(request),
                    title=path,
                    content=u"",
                    user_message=u"",
                    user=request.user,
                    ip_address=request.META['REMOTE_ADDR'],
                    article_kwargs={
                        'owner': request.user
                    }
                )
            buttons.append(PowerButton(url=POWERADMIN_WIKI_ARTICLE_URL.format(path=path), label=u'Ajuda'))

        context.update({
            'buttons': buttons,
            'readonly': readonly,
        })
        return super(PowerModelAdmin, self).render_change_form(request, context, add, change, form_url, obj)

    def button_view_dispatcher(self, request, object_id, command):
        obj = self.model._default_manager.get(pk=object_id)
        return getattr(self, command)(request, obj)  \
            or HttpResponseRedirect(request.META['HTTP_REFERER'])

    def related_lookup(self, request):
        data = {}
        if request.method == 'GET':
            if request.GET.has_key('object_id'):
                try:
                    obj = self.get_queryset(request).get(pk=request.GET.get('object_id'))
                    data = {"value": obj.pk, "label": u"%s" % obj}
                except: pass
        return HttpResponse(json.dumps(data), content_type='application/javascript')

    def get_urls(self):
        opts = self.model._meta
        buttons_urls = [url(r'^(\d+)/(%s)/$' % but.flag, self.wrap(self.button_view_dispatcher)) for but in self.buttons]
        buttons_urls.append(url(r'^lookup/related/$', self.wrap(self.related_lookup), name="%s_%s_related_lookup" % (opts.app_label, opts.object_name.lower())))
        return buttons_urls + super(PowerModelAdmin, self).get_urls()

    def wrap(self, view):
        from functools import update_wrapper
        def wrapper(*args, **kwargs):
            return self.admin_site.admin_view(view)(*args, **kwargs)
        return update_wrapper(wrapper, view)

    def get_buttons(self, request, object_id=None):
        return [b for b in self.buttons if b.visible]

    def get_changelist(self, request, **kwargs):
        from .views import PowerChangeList
        return PowerChangeList

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['buttons'] = self.get_buttons(request, None)

        c_url = resolve(request.path_info)

        if c_url.namespace:
            url_name = '%s:%s' % (c_url.namespace, c_url.url_name)
        else:
            url_name = '%s' % c_url.url_name

        try:
            admin_config = UserAdminConfig.objects.filter(user=request.user, url_name=url_name)[0]
            admin_old_url = admin_config.url_full_path

            admin_config.url_name = url_name
            admin_config.url_full_path = request.get_full_path()
            admin_config.save()
        except IndexError:
            admin_old_url = None
            admin_config = UserAdminConfig.objects.create(
                user=request.user,
                url_name=url_name,
                url_full_path=request.get_full_path(),
            )

        if admin_old_url == request.get_full_path():
            admin_old_url = None

        extra_context['admin_old_url'] = admin_old_url

        opts = self.model._meta
        app_label = opts.app_label

        multi_search_fields = []
        for field_opts in self.multi_search:
            attributes = {
                'size': '40',
            }

            if len(field_opts) == 4:
                attributes.update(field_opts[3])

            multi_search_fields.append({
                'name': field_opts[0],
                'label': field_opts[1],
                'value': request.GET.get(field_opts[0], ''),
                'attributes': ' '.join(['%s="%s"' % (k, v) for k, v in attributes.items()]),
            })

        buttons = self.get_buttons(request, None)

        if POWERADMIN_USE_WIKI:
            path = '{0}-{1}'.format(app_label.lower(), opts.object_name.lower())
            from wiki.models import Article, ArticleRevision, URLPath
            from django.contrib.sites.shortcuts import get_current_site

            if not URLPath.objects.filter(slug=path).count():
                if not URLPath.objects.count():
                    URLPath.create_root(
                        site=get_current_site(request),
                        title=u'Root',
                        content=u"",
                        request=request
                    )
                root = URLPath.objects.order_by('id')[0]

                URLPath.create_article(
                    root,
                    path,
                    site=get_current_site(request),
                    title=path,
                    content=u"",
                    user_message=u"",
                    user=request.user,
                    ip_address=request.META['REMOTE_ADDR'],
                    article_kwargs={
                        'owner': request.user
                    }
                )
            buttons.append(PowerButton(url=POWERADMIN_WIKI_ARTICLE_URL.format(path=path), label=u'Ajuda', attrs={'target': '_blank'}))

        context_data = {
            'buttons': buttons,
            'multi_search': True,
            'multi_search_fields': multi_search_fields,
            'admin_old_url': admin_old_url,
        }
        extra_context.update(context_data)
        return super(PowerModelAdmin, self).changelist_view(request, extra_context)


class PowerButton(object):
    flag = ''  # Usado para URLs fixas do botao, como na versao anterior
    url = ''  # Usado para informar diretamente a URL e assim permitir qualquer URL
    visible = True
    label = 'Label'
    attrs = {'class': 'historylink', }

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def get_url(self):
        return self.url or (self.flag + '/')


class PowerInlineModelAdmin(InlineModelAdmin):

    def has_change_permission(self, request, obj=None):
        change_permission = super(PowerInlineModelAdmin, self).has_change_permission(request, obj) # Alterar
        view = get_permission_codename('view', self.opts) # Visualizar
        browser = get_permission_codename('browser', self.opts) # Visualizar listagem
        if obj:
            return change_permission or request.user.has_perm("%s.%s" % (self.opts.app_label, view))
        return change_permission or request.user.has_perm("%s.%s" % (self.opts.app_label, browser))

    def _all_fields(self, request, obj=None):
        if self.fields:
            return self.fields
        if self.fieldsets:
            return flatten_fieldsets(self.get_fieldsets(request, obj))
        fields = [field.name for field in self.opts.local_fields]
        if 'id' in fields: fields.remove('id')
        return fields

    def get_readonly_fields(self, request, obj=None):
        change_permission = super(PowerInlineModelAdmin, self).has_change_permission(request, obj)
        view = get_permission_codename('view', self.opts)
        if not change_permission and request.user.has_perm("%s.%s" % (self.opts.app_label, view)):
            return self._all_fields(request, obj)
        return super(PowerInlineModelAdmin, self).get_readonly_fields(request, obj)


class PowerStackedInline(PowerInlineModelAdmin):
    template = 'admin/edit_inline/stacked.html'


class PowerTabularInline(PowerInlineModelAdmin):
    template = 'admin/edit_inline/tabular.html'
