from django.db import models
from django.forms import TextInput, Textarea
from django.contrib import admin
from django.utils.safestring import mark_safe

from core.models import *

import os
from core.apps import OSRun

from poweradmin.admin import PowerModelAdmin, PowerButton

from django.conf.urls import url
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render_to_response, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext


class TermoInline(admin.TabularInline):
    model = Termo
    extra = 0
    fields = ('busca', 'dtinicio', 'dtfinal', 'status', 'tot_twits',)
    readonly_fields = ('tot_twits', )


class ProjetoAdmin(PowerModelAdmin):
    list_display = ('nome', 'usuario', 'status', 'tot_twits',)
    fields = ('nome', 'objetivo', 'usuario', 'tot_twits')
    readonly_fields = ('usuario', 'tot_twits', )
    inlines = [TermoInline]

    def save_model(self, request, obj, form, change):
        obj.usuario = request.user
        super(ProjetoAdmin, self).save_model(request, obj, form, change)
        if os.path.exists('/var/webapp/twitsearch/twitsearch/crawler.sh'):
            OSRun('/var/webapp/twitsearch/twitsearch/crawler.sh&')

    def get_urls(self):
        return [
            url(r'^stats/(?P<id>.*)/$', self.admin_site.admin_view(self.stats), name='core_projeto_stats'),
            url(r'^nuvem/(?P<id>.*)/$', self.admin_site.admin_view(self.nuvem), name='core_projeto_nuvem'),
            url(r'^gephi/(?P<id>.*)/$', self.admin_site.admin_view(self.gephi_export),
                name='core_projeto_gephi_export'),
            ] + super(ProjetoAdmin, self).get_urls()

    def get_buttons(self, request, object_id):
        buttons = super(ProjetoAdmin, self).get_buttons(request, object_id)
        if object_id:
            obj = self.get_object(request, object_id)
            buttons.append(
                PowerButton(url=reverse('admin:core_projeto_stats', kwargs={'id': object_id, }),
                            label=u'Estatísticas'))
            buttons.append(
                PowerButton(url=reverse('admin:core_projeto_nuvem', kwargs={'id': object_id, }),
                            label=u'Nuvem de Palavras'))
        buttons.append(
            PowerButton(url=reverse('admin:core_projeto_gephi_export', kwargs={'id': object_id, }),
                        label=u'Exportação Gephi'))
        return buttons

    def stats(self, request, id):
        projeto = get_object_or_404(Projeto, pk=id)
        palavras = projeto.most_common()
        return render_to_response('core/stats.html', {
            'title': u'Estatísticas dos Twitters Obtidos',
            'projeto': projeto,
            'palavras': palavras
        }, RequestContext(request, ))

    def nuvem(self, request, id):
        projeto = get_object_or_404(Projeto, pk=id)
        return render_to_response('core/nuvem.html', {
            'title': u'Estatísticas dos Twitters Obtidos',
            'projeto': projeto,
        }, RequestContext(request, ))

    def gephi_export(self, request, id):
        projeto = get_object_or_404(Projeto, pk=id)
        return HttpResponseRedirect(reverse('admin:core_projeto_change', args=(id,)))


class HistoryInline(admin.TabularInline):
    model = FollowersHistory
    extra = 0
    fields = ('dt', 'followers', 'favourites')
    readonly_fields = fields


class TwitInline(admin.TabularInline):
    model = Tweet
    extra = 0
    fields = ('text', 'created_time', 'retweets', 'favorites')
    readonly_fields = fields


class UserAdmin(PowerModelAdmin):
    search_fields = ('username', 'name')
    list_filter = ('verified', )
    list_display = ('username', 'name', 'location', 'verified', 'followers_str', )
    fields = list_display
    readonly_fields = fields
    localized_fields = ('followers',)
    inlines = [HistoryInline, TwitInline]

    # Localização não funcionou
    def followers_str(self, obj):
        return '{:,}'.format(obj.followers).replace(',','.')
    followers_str.short_description = 'Followers'
    followers_str.admin_order_field = 'followers'


class TweetAdmin(PowerModelAdmin):
    search_fields = ('text', )
    list_filter = ('termo__projeto', 'termo')
    list_display = ('text', 'user', 'retweets', 'favorites', 'created_time')
    fields = ('text', 'retweets', 'favorites', 'user_link', 'termo', 'created_time', 'original_link', 'source')
    readonly_fields = fields

    def original_link(self, instance):
        if instance.retwit_id:
            return mark_safe("<a href='%s'>Original</a>" %
                             reverse('admin:core_tweet_change', args=[instance.retwit_id]))
        else:
            return '-'
    original_link.short_description = 'Retwitted Link'

    def user_link(self, instance):
        return mark_safe("<a href='%s'>%s</a>" %
                         (reverse('admin:core_tweetuser_change', args=[instance.user.twit_id]), instance.user.username))
    user_link.short_description = 'User Link'

    def source(self, instance):
        return mark_safe("<a href='https://www.twitter.com/%s/statuses/%s' target='_blank'>Twitter</a>" % (instance.user, instance.twit_id))
    source.short_description = 'Twitter Link'


class TermoAdmin(PowerModelAdmin):
    list_display = ('busca', 'projeto', 'dtinicio', 'ult_processamento', 'status', 'tot_twits',)

    def get_form(self, request, obj=None, **kwargs):
        form = super(TermoAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['busca'].widget.attrs['style'] = 'width: 30em;'
        return form


admin.site.register(Projeto, ProjetoAdmin)
admin.site.register(TweetUser, UserAdmin)
admin.site.register(Tweet, TweetAdmin)
admin.site.register(Termo, TermoAdmin)
admin.site.register(Processamento)
admin.site.register(LockProcessamento)
