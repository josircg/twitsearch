from django.urls import path
from django.conf.urls import url

from core.views import visao, stats, index, solicitar_csv, backup_json, exclui_json,\
    nuvem, create_graph, gerar_gephi, solicita_busca, get_source, importacao_arquivo

from core.api import redes, termos, projetos

urlpatterns = [
    url(r'^$', index),
    url(r'^visao/$', visao),
    url(r'^solicita_busca/(?P<termo_id>\d+)/$', solicita_busca, name='solicita_busca'),
    url(r'^estatistica/(?P<project_id>\d+)/$', stats, name='core_projeto_stats'),
    url(r'^backup_json/(?P<project_id>\d+)/$', backup_json, name='backup_json'),
    url(r'^exclui_json/(?P<project_id>\d+)/$', exclui_json, name='exclui_json'),
    url(r'^solicitar_csv/(?P<project_id>\d+)/$', solicitar_csv, name='solicitar_csv'),
    url(r'^nuvem/(?P<project_id>\d+)/$', nuvem, name='core_projeto_nuvem'),
    url(r'^nuvem/(?P<project_id>\d+)/(?P<modelo>\d+)/$', nuvem, name='core_projeto_nuvem'),
    url(r'^grafo/(?P<project_id>\d+)/$', create_graph, name='graph'),
    url(r'^gerar_gephi/(?P<project_id>\d+)/$', gerar_gephi, name='gerar_gephi'),
    url(r'^source/(?P<tweet_id>\d+)/$', get_source, name='get_source'),
    url(r'^importacao_arquivo/', importacao_arquivo, name='importacao_arquivo'),
    path('api/redes/', redes, name='redes'),
    path('api/projetos/', projetos, name='projeto'),
    path('api/projetos/<str:status>', projetos, name='projeto'),
    path('api/termos/<int:rede_id>', termos, name='termos'),

]