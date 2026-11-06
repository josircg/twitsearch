from typing import Any

from django.contrib import admin, messages
from django.forms.models import BaseInlineFormSet
from django.urls import reverse
from django.utils.html import format_html

from core.models import TermoStatus
from .models import Canal, Lista, APIKeys, Categoria
from poweradmin.admin import PowerModelAdmin, PowerButton, PowerTabularInline, PowerInlineModelAdmin


@admin.register(Categoria)
class CategoriaAdmin(PowerModelAdmin):
    list_display = ('nome', 'tot_canais',)


@admin.register(Canal)
class CanalAdmin(PowerModelAdmin):
    list_display = ('username', 'titulo', 'status', 'num_mensagens', 'num_participantes')
    list_filter = ('status',)
    search_fields = ('username', 'titulo', 'lista__nome')
    actions = 'disable',

    @admin.action(description='Desabilita Canal')
    def disable(self, request, queryset):
        tot_reg = 0
        for reg in queryset:
            reg.status = Canal.Status.INATIVO
            reg.save()
            tot_reg += 1
        messages.info(request, f'{tot_reg} canais desativados')
        return


class ReadOnlyInlineFormSet(BaseInlineFormSet):
    """Formset que ignora o POST: é só exibição, nunca valida nem grava nada."""

    def __init__(self, data=None, files=None, *args, **kwargs):
        super().__init__(None, None, *args, **kwargs)

    def is_valid(self):
        return True


class CanalReadOnlyInline(PowerTabularInline):
    """Lista os canais da lista somente para leitura.

    Usa um template próprio sem os inputs hidden por linha (id/fk) que o
    inline padrão do Django renderiza, pois eles estouram
    DATA_UPLOAD_MAX_NUMBER_FIELDS em listas com muitos canais.
    """
    model = Lista.canais.through
    formset = ReadOnlyInlineFormSet
    template = 'admin/telegram/canais_readonly_inline.html'
    verbose_name_plural = 'Canais'
    extra = 0
    fields = ('username', 'titulo', 'status')
    readonly_fields = ('username', 'titulo', 'status')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('canal').order_by('canal__username')

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Canal')
    def username(self, obj):
        return format_html('<a href="{}">{}</a>',
                           reverse('admin:telegram_canal_change', args=(obj.canal_id,)), obj.canal.username)

    @admin.display(description='Título')
    def titulo(self, obj):
        return obj.canal.titulo or ''

    @admin.display(description='Status')
    def status(self, obj):
        return obj.canal.get_status_display()


@admin.register(Lista)
class ListaAdmin(PowerModelAdmin):
    list_display = ('nome', 'publica', 'tot_canais', 'canais_ativos')
    fields = ('nome', 'publica',)
    inlines = (CanalReadOnlyInline,)

    def save_model(self, request, obj, form, change):
        obj.dono = request.user
        super(ListaAdmin, self).save_model(request, obj, form, change)


@admin.register(APIKeys)
class APIKeysAdmin(PowerModelAdmin):
    list_display = ('titulo', 'user', 'status')

    def get_queryset(self, request):
        """Filtra a listagem para exibir apenas os registros do usuário logado."""
        qs = super().get_queryset(request)

        # Superusuários (admins) continuam vendo todos os registros
        if request.user.is_superuser:
            return qs

        return qs.filter(user=request.user)

    def save_model(self, request, obj, form, change):
        obj.user = request.user
        super(APIKeysAdmin, self).save_model(request, obj, form, change)


@admin.register(TermoStatus)
class TermoStatusAdmin(PowerModelAdmin):
    list_display = ('projeto', 'termo', 'status', 'ult_processo')
    list_filter = ('status',)
    readonly_fields = ('projeto', 'termo', 'status', 'ult_processo')

    def get_queryset(self, request):
        """Filtra a listagem para exibir apenas os registros do usuário logado."""
        qs = super().get_queryset(request)

        # Superusuários (admins) continuam vendo todos os registros
        return qs.filter(rede_id=4)

    def projeto(self, obj):
        return obj.termo.projeto
    projeto.short_description = 'Projeto'
    projeto.admin_order_field = 'termo__projeto__nome'