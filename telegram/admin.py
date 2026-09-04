from typing import Any

from django.contrib import admin, messages

from core.models import TermoStatus
from .models import Canal, Lista, APIKeys, Categoria
from poweradmin.admin import PowerModelAdmin, PowerButton, PowerTabularInline, PowerInlineModelAdmin


@admin.register(Categoria)
class CategoriaAdmin(PowerModelAdmin):
    list_display = ('nome', 'tot_canais',)


@admin.register(Canal)
class CanalAdmin(PowerModelAdmin):
    list_display = ('username', 'titulo', 'status', 'num_mensagens',)
    list_filter = ('status',)
    search_fields = ('username', 'titulo',)
    actions = 'disable',

    @admin.action(description='Desabilita Canal')
    def disable(self, request, queryset):
        tot_reg = 0
        for reg in queryset:
            reg.status = Canal.Status.DESATIVADO
            reg.save()
            tot_reg += 1
        messages.info(request, f'{tot_reg} canais desativados')
        return


class CanalTabularInline(PowerTabularInline):
    model = Lista.canais.through
    autocomplete_fields = ['canal']
    extra = 0


@admin.register(Lista)
class ListaAdmin(PowerModelAdmin):
    list_display = ('nome', 'publica', 'tot_canais',)
    fields = ('nome', 'publica',)
    inlines = (CanalTabularInline,)

    def save_model(self, request, obj, form, change):
        obj.dono = request.user
        super(ListaAdmin, self).save_model(request, obj, form, change)


@admin.register(APIKeys)
class APIKeysAdmin(PowerModelAdmin):
    list_display = ('titulo', )

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