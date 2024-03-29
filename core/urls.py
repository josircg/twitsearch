from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static

from core.views import visao, stats, index, solicitar_csv, nuvem, create_graph, gerar_gephi, solicita_busca

urlpatterns = [
    url(r'^$', index),
    url(r'^visao/$', visao),
    url(r'^solicita_busca/(?P<id>\d+)/$', solicita_busca, name='solicita_busca'),
    url(r'^estatistica/(?P<id>\d+)/$', stats, name='core_projeto_stats'),
    url(r'^nuvem/(?P<id>\d+)/$', nuvem, name='core_projeto_nuvem'),
    url(r'^solicitar_csv/(?P<id>\d+)/$', solicitar_csv, name='solicitar_csv'),
    url(r'^grafo/(?P<id_projeto>\d+)/$', create_graph, name='graph'),
    url(r'^gerar_gephi/(?P<id_projeto>\d+)/$', gerar_gephi, name='gerar_gephi'),
    # url(r'^exemplo/$', use_seaborn, name='exemplo'),
]