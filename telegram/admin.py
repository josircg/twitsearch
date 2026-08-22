from typing import Any

from django.contrib import admin

from .models import Canal, Lista, APIKeys
from poweradmin.admin import PowerModelAdmin, PowerButton, PowerTabularInline, PowerInlineModelAdmin


@admin.register(Canal)
class CanalAdmin(PowerModelAdmin):
    list_display = ('username', 'titulo', 'num_participantes',)


@admin.register(Lista)
class ListaAdmin(PowerModelAdmin):
    list_display = ('nome', 'publica', 'tot_canais',)


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

