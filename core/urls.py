from django.conf.urls import url

from core.views import visao, stats, index

urlpatterns = [
    url(r'^$', index),
    url(r'^visao/$', visao),
    url(r'^estatistica/(?P<id>\w+)/$', stats, name='core_projeto_stats'),
]