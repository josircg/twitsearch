from django.db import models
from django.forms import TextInput, Textarea
from django.contrib import admin
from django.utils.safestring import mark_safe

from core.models import *
from twitsearch.settings import SITE_HOST
from poweradmin.admin import PowerModelAdmin, PowerButton


class TermoInline(admin.TabularInline):
    model = Termo
    extra = 0
    fields = ('busca', 'dtinicio', 'dtfinal', 'status', 'tot_twits',)
    readonly_fields = ('tot_twits', )


class ProjetoAdmin(PowerModelAdmin):
    fields = ('nome', 'objetivo', 'usuario', 'tot_twits')
    readonly_fields = ('usuario', 'tot_twits', )
    inlines = [TermoInline]

    def save_model(self, request, obj, form, change):
        obj.usuario = request.user
        super(ProjetoAdmin, self).save_model(request, obj, form, change)


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
    list_filter = ('verified',)
    list_display = ('username', 'location', 'verified', 'followers', )
    inlines = [HistoryInline, TwitInline]


class TweetAdmin(admin.ModelAdmin):
    list_display = ('text', 'user', 'retweets')
    fields = ('text', 'retweets', 'favorites', 'user_link', 'termo', 'created_time', 'original_link')
    readonly_fields = fields

    def original_link(self, instance):
        if instance.retwit_id:
            return mark_safe("<a href='%sadmin/core/tweet/%s/change'>Original</a>" %
                             (SITE_HOST, instance.retwit_id))
        else:
            return '-'
    original_link.short_description = 'Original Twitter'

    def user_link(self, instance):
        return mark_safe("<a href='%sadmin/core/tweetuser/%s/change'>%s</a>" %
                         (SITE_HOST, instance.user.twit_id, instance.user.username))
    user_link.short_description = 'User'

    '''
    def formfield_for_dbfield(self, db_field, **kwargs):
        field = super(TweetAdmin, self).formfield_for_dbfield(db_field, **kwargs)
        if db_field.name == 'twit_id':
            field.widget.attrs['size'] = '16'
            field.widget.attrs['class'] = ''

        if db_field.name == 'text':
            field.widget.attrs['size'] = '80'
            field.widget.attrs['class'] = ''
        return field
    '''


admin.site.register(Projeto, ProjetoAdmin)
admin.site.register(TweetUser, UserAdmin)
admin.site.register(Tweet, TweetAdmin)
admin.site.register(Termo)
admin.site.register(Processamento)

