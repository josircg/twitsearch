from django.db import models
from django.contrib import admin
from django.conf import settings

from core.models import *

from core.apps import export_tags_action, export_extra_action, detach_action

from poweradmin.admin import PowerModelAdmin, PowerButton

from django.conf.urls import url
from django.urls import reverse
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from urllib.parse import urlencode


def get_object_from_path(request, model):
    object_id = request.META['PATH_INFO'].strip('/').split('/')[-2]
    try:
        object_id = int(object_id)
    except ValueError:
        return None
    return model.objects.get(pk=object_id)


def projeto_readonly(usuario, projeto):
    if usuario.is_superuser:
        readonly = False
    else:
        grupos = usuario.groups
        if projeto and grupos and projeto.grupo:
            readonly = not grupos.filter(id=projeto.grupo.id).exists()
        else:
            readonly = True
    return readonly


class TermoInline(admin.TabularInline):
    model = Termo
    extra = 0
    fields = ('busca', 'tipo_busca', 'dtinicio', 'dtfinal', 'language', 'status', 'last_count',)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            readonly = projeto_readonly(request.user, obj)
        else:
            readonly = False

        if not readonly:
            return 'last_count',
        else:
            return 'busca', 'tipo_busca', 'dtinicio', 'dtfinal', 'language', 'status', 'last_count'

    def has_add_permission(self, request):
        projeto = get_object_from_path(request, Projeto)
        return not projeto_readonly(request.user, projeto)

    def has_delete_permission(self, request, obj=None):
        return not projeto_readonly(request.user, obj)


class ProjetoAdmin(PowerModelAdmin):
    list_display = ('nome', 'usuario', 'status', 'tot_twits',)
    search_fields = ('nome',)
    fields = ('nome', 'objetivo', 'tot_twits', 'tot_retwits', 'tot_favorites', 'usuario', 'grupo')
    inlines = [TermoInline]

    def get_actions(self, request):
        actions = super(ProjetoAdmin, self).get_actions(request)
        if not request.user.is_superuser:
            if 'delete_selected' in actions:
                del actions['delete_selected']
        return actions

    def get_fields(self, request, obj=None):
        if obj:
            if request.user.is_superuser:
                return 'nome', 'objetivo', 'tot_twits', 'tot_retwits', 'alcance', 'usuario', 'grupo'
            else:
                return 'nome', 'objetivo', 'tot_twits', 'tot_retwits', 'alcance', 'usuario'
        else:
            return 'nome', 'objetivo',

    def save_model(self, request, obj, form, change):
        if not change:
            obj.usuario = request.user
            obj.grupo = request.user.groups.first()
        super(ProjetoAdmin, self).save_model(request, obj, form, change)
        # if os.path.exists('/var/webapp/twitsearch/twitsearch/crawler.sh'):
        #    OSRun('/var/webapp/twitsearch/twitsearch/crawler.sh')

    def get_urls(self):
        return [
            url(r'^visao/(?P<id>.*)/$', self.admin_site.admin_view(self.visao), name='core_projeto_visao'),
            ] + super(ProjetoAdmin, self).get_urls()

    def get_buttons(self, request, object_id):
        buttons = super(ProjetoAdmin, self).get_buttons(request, object_id)
        if object_id:
            buttons.append(
                PowerButton(url=reverse('core_projeto_stats', kwargs={'id': object_id, }),
                            label=u'Estatísticas'))
            buttons.append(
                PowerButton(url=reverse('core_projeto_nuvem', kwargs={'id': object_id, }),
                            label=u'Nuvem de Palavras'))
            buttons.append(
                PowerButton(url=reverse('admin:core_projeto_visao', kwargs={'id': object_id, }),
                            label=u'Visão'))
            if settings.AWS_PROFILE:
                buttons.append(
                    PowerButton(url=reverse('backup_json', kwargs={'id': object_id, }),
                                label=u'Backup'))
            buttons.append(
                PowerButton(url=reverse('exclui_json', kwargs={'id': object_id, }),
                            label=u'Exclui JSON'))
            buttons.append(
                PowerButton(url='https://developer.twitter.com/en/docs/twitter-api/v1/rules-and-filtering/overview/standard-operators', label=u'Como utilizar a busca', attrs={'target': '_blank'})
            )
            buttons.append(
                PowerButton(url=reverse('graph', kwargs={'id_projeto': object_id}), label='Grafo')
            )

        return buttons

    def get_readonly_fields(self, request, obj=None):
        if obj:
            readonly = projeto_readonly(request.user, obj)
        else:
            return 'usuario', 'tot_twits', 'tot_retwits'

        if not readonly:
            if request.user.is_superuser:
                return 'usuario', 'tot_twits', 'tot_retwits', 'alcance'
            else:
                return 'usuario', 'tot_twits', 'tot_retwits', 'alcance', 'grupo'
        else:
            return 'nome', 'objetivo', 'usuario', 'grupo', 'tot_twits', 'tot_retwits', 'alcance'

    def visao(self, request, id):
        projeto = get_object_or_404(Projeto, pk=id)
        return render_to_response('core/visao.html', {
            'title': u'Envio de Dados para o Visão',
            'projeto': projeto,
        }, RequestContext(request, ))


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
    fields = ('url_str', 'text', 'created_time', 'retweets', 'favorites')
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def url_str(self, obj):
        return obj.url
    url_str.short_description = 'Link'


class RetweetInline(admin.TabularInline):
    model = Retweet
    extra = 0
    fields = ('id', 'tweet', 'created_time',)
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
        ('q4', 'Termo', ['termo']),
    )

    list_filter = ('termo__projeto', 'language',)
    list_display = ('text', 'user', 'retweets', 'favorites', 'created_time')
    list_csv = ('text', 'user', 'retweets', 'favorites', 'created_time',)
    fields = ('text', 'retweets', 'favorites', 'user_link', 'termo', 'created_time', 'language', 'url')
    readonly_fields = fields
    list_per_page = 30

    def lookup_allowed(self, lookup, value):
        if lookup == 'tweetinput__processamento__id':
            return True
        return super(TweetAdmin, self).lookup_allowed(lookup, value)

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
        ('q1', 'Tweet Original', ['parent_id']),
        ('q2', 'Twitter User', ['user__username']),
        ('q3', 'Retweet ID', ['retweet_id']),
    )
    list_display = ('retweet_id', 'user', 'created_time', 'tweet', 'type', 'tweet_dif')
    list_per_page = 30

    raw_id_fields = ('user', 'tweet')


class TermoAdmin(PowerModelAdmin):
    search_fields = ('busca',)
    list_filter = ('status',)
    list_display = ('busca', 'projeto', 'dtinicio', 'ult_processamento', 'status', 'last_count',)

    def get_form(self, request, obj=None, **kwargs):
        form = super(TermoAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['busca'].widget.attrs['style'] = 'width: 30em;'
        return form

    def get_buttons(self, request, object_id):
        buttons = super(TermoAdmin, self).get_buttons(request, object_id)
        if object_id:
            buttons.append(
                PowerButton(url=reverse('solicita_busca', kwargs={'id': object_id, }),
                            label=u'Busca Local'))
        return buttons


class ProcessamentoAdmin(PowerModelAdmin):
    list_display = ('termo', 'tipo', 'dt', 'twit_id', 'tot_twits')
    raw_id_fields = ('termo', )
    list_filter = ('tipo', 'dt')

    def get_buttons(self, request, object_id):
        buttons = super(ProcessamentoAdmin, self).get_buttons(request, object_id)
        if object_id:
            buttons.append(
                PowerButton(url='/admin/core/tweet/?tweetinput__processamento__id=%d' % object_id,
                            label="Tweets", attrs={'target': '_blank'})
            )
        return buttons


admin.site.register(Projeto, ProjetoAdmin)
admin.site.register(TweetUser, UserAdmin)
admin.site.register(Retweet, RetweetAdmin)
admin.site.register(Tweet, TweetAdmin)
admin.site.register(Termo, TermoAdmin)
admin.site.register(Processamento, ProcessamentoAdmin)
