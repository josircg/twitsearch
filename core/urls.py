from django.urls import path, re_path
from django.views.generic import RedirectView

from core.views import visao, stats, index, solicitar_csv, backup_json, exclui_json,\
    nuvem, create_graph, gerar_gephi, solicita_busca, painel, get_source, importacao_arquivo, status_coleta

from telegram.views import canal_mensagens, importacao_canais, importar_lista, lista_canais, telegram_project, \
    editar_projeto

from core.api import (redes, termos, projetos, termos_by_id, processo, canais_telegram,
                      processo_rede_get, processo_rede_set)

urlpatterns = [
    re_path(r'^$', index),
    re_path(r'^visao/$', visao),
    path('painel/', painel, name='painel'),
    re_path(r'^solicita_busca/(?P<termo_id>\d+)/$', solicita_busca, name='solicita_busca'),
    re_path(r'^estatistica/(?P<project_id>\d+)/$', stats, name='core_projeto_stats'),
    re_path(r'^estatistica/(?P<project_id>\d+)/(?P<termo_id>\d+)/$', stats, name='core_projeto_stats'),
    re_path(r'^backup_json/(?P<project_id>\d+)/$', backup_json, name='backup_json'),
    re_path(r'^exclui_json/(?P<project_id>\d+)/$', exclui_json, name='exclui_json'),
    re_path(r'^solicitar_csv/(?P<project_id>\d+)/$', solicitar_csv, name='solicitar_csv'),
    re_path(r'^nuvem/(?P<project_id>\d+)/$', nuvem, name='core_projeto_nuvem'),
    re_path(r'^nuvem/(?P<project_id>\d+)/(?P<modelo>\d+)/$', nuvem, name='core_projeto_nuvem'),
    re_path(r'^grafo/(?P<project_id>\d+)/$', create_graph, name='graph'),
    re_path(r'^gerar_gephi/(?P<project_id>\d+)/$', gerar_gephi, name='gerar_gephi'),
    re_path(r'^source/(?P<tweet_id>\d+)/$', get_source, name='get_source'),
    path('tweets/importar/', importacao_arquivo, name='importacao_arquivo'),
    path('telegram/projetos/novo/', telegram_project, name='telegram_project'),
    path('telegram/projetos/<int:pk>/editar/', editar_projeto, name='editar_projeto'),
    path('telegram/listas/', lista_canais, name='lista_canais'),
    path('telegram/listas/importar/', importar_lista, name='importar_lista'),
    path('telegram/canais/importar/', importacao_canais, name='importacao_canais'),
    path('telegram/canais/<int:pk>/', canal_mensagens, name='canal_mensagens'),
    path('termos/<int:termo_id>/status/', status_coleta, name='status_coleta'),
    # rotas antigas (redirecionam com 301 para as novas, preservando a query string)
    re_path(r'^importacao_arquivo/$', RedirectView.as_view(pattern_name='importacao_arquivo', permanent=True, query_string=True)),
    path('telegram_project/', RedirectView.as_view(pattern_name='telegram_project', permanent=True, query_string=True)),
    path('telegram_project/importar_lista/', RedirectView.as_view(pattern_name='importar_lista', permanent=True, query_string=True)),
    path('telegram_project/<int:pk>/', RedirectView.as_view(pattern_name='editar_projeto', permanent=True, query_string=True)),
    path('telegram/lista_canais/', RedirectView.as_view(pattern_name='lista_canais', permanent=True, query_string=True)),
    path('telegram/importacao_canais/', RedirectView.as_view(pattern_name='importacao_canais', permanent=True, query_string=True)),
    path('telegram/canal/<int:pk>/', RedirectView.as_view(pattern_name='canal_mensagens', permanent=True, query_string=True)),
    path('termo_stat/<int:termo_id>', RedirectView.as_view(pattern_name='status_coleta', permanent=True, query_string=True)),
    path('api/redes/', redes, name='redes'),
    path('api/eixos/', projetos, name='eixos'),
    path('api/canais_telegram/', canais_telegram, name='canais_telegram'),
    path('api/projetos/', projetos, name='projeto'),
    path('api/projetos/<str:status>', projetos, name='projeto'),
    path('api/processo/<int:processo_id>', processo, name='processo'),
    path('api/termos/<int:rede_id>', termos, name='termos'),
    path('api/termos/<int:termo_id>/detail', termos_by_id, name='termos'),
    path('api/get_processo/<int:termo_id>/<int:rede_id>', processo_rede_get, name='projeto'),
    path('api/update_processo/<int:termo_id>/<int:rede_id>/<str:processo>', processo_rede_set, name='projeto'),
]