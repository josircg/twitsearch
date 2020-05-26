import io

from django.conf import settings
from django.db import models
from django.contrib import admin
from django.utils.safestring import mark_safe
from wordcloud import WordCloud

from core.models import *

import os
from core.apps import OSRun, export_tags_action, export_extra_action, detach_action

from poweradmin.admin import PowerModelAdmin, PowerButton

from django.conf.urls import url
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render_to_response, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from urllib.parse import urlencode

class TermoInline(admin.TabularInline):
    model = Termo
    extra = 0
    fields = ('busca', 'dtinicio', 'dtfinal', 'status', 'tot_twits',)
    readonly_fields = ('tot_twits', )


class ProjetoAdmin(PowerModelAdmin):
    list_display = ('nome', 'usuario', 'status', 'tot_twits',)
    fields = ('nome', 'objetivo', 'usuario', 'tot_twits', 'tot_retwits')
    readonly_fields = ('usuario', 'tot_twits', 'tot_retwits')
    inlines = [TermoInline]

    def save_model(self, request, obj, form, change):
        obj.usuario = request.user
        super(ProjetoAdmin, self).save_model(request, obj, form, change)
        if os.path.exists('/var/webapp/twitsearch/twitsearch/crawler.sh'):
            OSRun('/var/webapp/twitsearch/twitsearch/crawler.sh&')

    def get_urls(self):
        return [
            url(r'^visao/(?P<id>.*)/$', self.admin_site.admin_view(self.visao), name='core_projeto_visao'),
            url(r'^gephi/(?P<id>.*)/$', self.admin_site.admin_view(self.gephi_export),
                name='core_projeto_gephi_export'),
            ] + super(ProjetoAdmin, self).get_urls()

    def get_buttons(self, request, object_id):
        buttons = super(ProjetoAdmin, self).get_buttons(request, object_id)
        if object_id:
            obj = self.get_object(request, object_id)
            buttons.append(
                PowerButton(url=reverse('core_projeto_stats', kwargs={'id': object_id, }),
                            label=u'Estatísticas'))
            buttons.append(
                PowerButton(url=reverse('core_projeto_nuvem', kwargs={'id': object_id, }),
                            label=u'Nuvem de Palavras'))
            buttons.append(
                PowerButton(url=reverse('admin:core_projeto_gephi_export', kwargs={'id': object_id, }),
                            label=u'Exportação Gephi'))
            buttons.append(
                PowerButton(url=reverse('admin:core_projeto_visao', kwargs={'id': object_id, }),
                            label=u'Visão'))
            buttons.append(
                PowerButton(url=u'https://developer.twitter.com/en/docs/tweets/search/guides/standard-operators', label=u'bookmark da explicação dos operadores', attrs={'target': '_blank'})
            )
            buttons.append(
                PowerButton(url=reverse('graph', kwargs={'id_projeto': object_id}), label='Grafo')
            )

        return buttons

    def visao(self, request, id):
        projeto = get_object_or_404(Projeto, pk=id)
        return render_to_response('core/visao.html', {
            'title': u'Envio de Dados para o Visão',
            'projeto': projeto,
        }, RequestContext(request, ))

    @staticmethod
    def gephi_export(self, request, id):
        projeto = get_object_or_404(Projeto, pk=id)
        return HttpResponseRedirect(reverse('admin:core_projeto_change', args=(id,)))


class HistoryInline(admin.TabularInline):
    model = FollowersHistory
    extra = 0
    fields = ('dt', 'followers', 'favourites')
    readonly_fields = fields

    def has_add_permission(self, request):
        return False


class TwitInline(admin.TabularInline):
    model = Tweet
    extra = 0
    fields = ('text', 'created_time', 'retweets', 'favorites')
    readonly_fields = fields

    def has_add_permission(self, request):
        return False


class RetweetInline(admin.TabularInline):
    model = Retweet
    extra = 0
    fields = ('tweet', 'created_time',)
    readonly_fields = ('tweet', 'created_time',)

    def has_add_permission(self, request):
        return False


class UserAdmin(PowerModelAdmin):
    search_fields = ('username', 'name')
    list_filter = ('verified', )
    list_display = ('username', 'name', 'location', 'verified', 'followers_str', )
    fields = list_display
    readonly_fields = fields
    localized_fields = ('followers',)
    inlines = [HistoryInline, TwitInline, RetweetInline]

    # Localização não funcionou
    def followers_str(self, obj):
        return '{:,}'.format(obj.followers).replace(',','.')
    followers_str.short_description = 'Followers'
    followers_str.admin_order_field = 'followers'


class TweetAdmin(PowerModelAdmin):
    multi_search = (
        ('q1', 'Texto', ['text']),
        ('q2', 'Usuário', ['user__username']),
        ('q3', 'ID', ['twit_id']),
    )

    list_filter = ('termo__projeto', 'termo', 'language',)
    list_display = ('text', 'user', 'retweets', 'favorites', 'created_time')
    list_csv = ('text', 'user', 'retweets', 'favorites', 'created_time',)
    fields = ('text', 'retweets', 'favorites', 'user_link', 'termo', 'created_time', 'language', 'url')
    readonly_fields = fields
    list_per_page = 30

    def user_link(self, instance):
        return mark_safe("<a href='%s'>%s</a>" %
                         (reverse('admin:core_tweetuser_change', args=[instance.user.twit_id]), instance.user.username))
    user_link.short_description = 'User Link'

    def source(self, instance):
        return mark_safe(self.tweet_url)
    source.short_description = 'Twitter Link'

    def get_actions(self, request):
        actions = super(TweetAdmin, self).get_actions(request)

        detach = detach_action()
        actions['detach'] = (detach, 'detach', detach.short_description)

        export = export_tags_action()
        actions['export_tags'] = (export, 'export_tags', export.short_description)

        extra = export_extra_action()
        actions['export_extra'] = (extra, 'export_extra', extra.short_description)

        return actions


    def get_buttons(self, request, object_id):
       buttons = super(TweetAdmin, self).get_buttons(request, object_id)
       if object_id:
           buttons.append(
               PowerButton(url='%s?%s' % (reverse('admin:core_retweet_changelist'), urlencode({'q1': object_id})),
                           label=u'Retweets'))
       return buttons

#    def get_urls(self):
#        return [
#            url(r'^retweet/(?P<id>.*)/$', self.admin_site.admin_view(self.r),
#                name='core_retweet'),
#            ] + super(TweetAdmin, self).get_urls()


class RetweetAdmin(PowerModelAdmin):
    multi_search = (
        ('q1', 'Tweet Original', ['tweet__twit_id']),
        ('q2', 'Twitter User', ['user__username']),
        ('q3', 'Retweet ID', ['retweet_id']),
    )
    list_display = ('user', 'created_time', 'tweet', 'tweet_dif')
    list_per_page = 30

    raw_id_fields = ('user', 'tweet')


class TermoAdmin(PowerModelAdmin):
    list_display = ('busca', 'projeto', 'dtinicio', 'ult_processamento', 'status', 'tot_twits',)

    def get_form(self, request, obj=None, **kwargs):
        form = super(TermoAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['busca'].widget.attrs['style'] = 'width: 30em;'
        return form


class ProcessamentoAdmin(PowerModelAdmin):
    list_display = ('termo', 'tipo', 'dt', 'twit_id', 'tot_twits')


admin.site.register(Projeto, ProjetoAdmin)
admin.site.register(TweetUser, UserAdmin)
admin.site.register(Retweet, RetweetAdmin)
admin.site.register(Tweet, TweetAdmin)
admin.site.register(Termo, TermoAdmin)
admin.site.register(Processamento, ProcessamentoAdmin)
admin.site.register(LockProcessamento)
