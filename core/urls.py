from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static

from core.views import visao, stats, index, solicitar_csv, nuvem

urlpatterns = [
    url(r'^$', index),
    url(r'^visao/$', visao),
    url(r'^estatistica/(?P<id>\d+)/$', stats, name='core_projeto_stats'),
    url(r'^nuvem/(?P<id>\d+)/$', nuvem, name='core_projeto_nuvem'),
    url(r'^solicitar_csv/(?P<id>\d+)/$', solicitar_csv, name='solicitar_csv'),
]