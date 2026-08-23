from django.urls import path
from django.urls import path, re_path

from core.views import visao, stats, index, solicitar_csv, backup_json, exclui_json,\
    nuvem, create_graph, gerar_gephi, solicita_busca, get_source, importacao_arquivo, status_coleta

from telegram.views import importacao_canais

from core.api import redes, termos, projetos, termos_by_id, processo, canais_telegram

urlpatterns = [
    re_path(r'^$', index),
    re_path(r'^visao/$', visao),
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
    re_path(r'^importacao_arquivo/', importacao_arquivo, name='importacao_arquivo'),
    path(r'telegram/importacao_canais/', importacao_canais, name='importacao_canais'),
    path('termo_stat/<int:termo_id>', status_coleta, name='status_coleta'),
    path('api/redes/', redes, name='redes'),
    path('api/eixos/', projetos, name='eixos'),
    path('api/canais_telegram/', canais_telegram, name='canais_telegram'),
    path('api/projetos/', projetos, name='projeto'),
    path('api/projetos/<str:status>', projetos, name='projeto'),
    path('api/processo/<int:processo_id>', processo, name='processo'),
    path('api/termos/<int:rede_id>', termos, name='termos'),
    path('api/termos/<int:termo_id>/detail', termos_by_id, name='termos'),

]