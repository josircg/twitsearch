from typing import Any

from django.contrib import admin

from .models import Canal, Lista, APIKeys, Categoria
from poweradmin.admin import PowerModelAdmin, PowerButton, PowerTabularInline, PowerInlineModelAdmin


@admin.register(Categoria)
class CategoriaAdmin(PowerModelAdmin):
    list_display = ('nome', 'tot_canais',)


@admin.register(Canal)
class CanalAdmin(PowerModelAdmin):
    list_display = ('username', 'titulo', 'status', 'num_participantes',)
    list_filter = ('status',)
    search_fields = ('username', 'titulo',)


class CanalTabularInline(PowerTabularInline):
    model = Lista.canais.through
    autocomplete_fields = ['canal']
    extra = 1


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

