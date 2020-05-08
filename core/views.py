import datetime
import os
from threading import Thread

from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, render_to_response, redirect

# Create your views here.

from django.shortcuts import render
from django.http import JsonResponse
import requests
from django.template import RequestContext
from django.urls import reverse
from wordcloud import WordCloud

from core.apps import generate_tags_file
from core.models import Projeto, Tweet, Processamento, PROC_TAGS, PROC_IMPORTACAO
from twitsearch.settings import BASE_DIR


def index(request):
    return render(request, 'index.html', context={'hello': 'world'})


def visao(request):
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    r = requests.post("http://beta.visao.ibict.br/api/authenticate/",
                      headers=headers,
                      json={'j_username': 'josir', 'j_password': '123@mudar',
                            'remember-me': True})

    # r = requests.get("http://beta.visao.ibict.br/api/authentication/",
    #                  params={'j_username': 'josir', 'j_password': '123@mudar',
    #                          'remember-me': 'undefined', 'submit': 'Login'})
    r.headers
    return r
    # return r JsonResponse({'data': 'ok'})


def stats(request, id):
    projeto = get_object_or_404(Projeto, pk=id)
    palavras = projeto.most_common()
    top_tweets = Tweet.objects.filter(termo__projeto_id=id).order_by('favorites')[:3]
    proc_tags = Processamento.objects.filter(termo=projeto.termo_set.all()[0],tipo=PROC_TAGS)
    proc_importacao = Processamento.objects.filter(termo__projeto=projeto, tipo=PROC_IMPORTACAO)
    if proc_tags > proc_importacao:
        exportacao = 'tags-%d.zip' % projeto.id

    return render_to_response('core/stats.html', {
        'title': u'Estatísticas do Projeto',
        'projeto': projeto,
        'palavras': palavras,
        'top_tweets': top_tweets,
        'download': download,
    }, RequestContext(request, ))


def nuvem(request, id):
    projeto = get_object_or_404(Projeto, pk=id)
    cloud = WordCloud(width=1200, height=800, max_words=60, scale=2, background_color='white')
    palavras = dict(projeto.most_common())
    cloud.generate_from_frequencies(palavras)
    path = os.path.join(BASE_DIR, 'media', 'nuvens')

    if not os.path.exists(path):
        if not os.path.exists(settings.MEDIA_ROOT):
            os.mkdir(settings.MEDIA_ROOT) # dir media
        os.mkdir(os.path.join(settings.MEDIA_ROOT, 'nuvens')) # path

    filename = 'nuvem-%s.png' % projeto.pk
    cloud.to_file(os.path.join(path, filename))

    return render_to_response('core/nuvem.html', {
        'title': u'Estatísticas dos Twitters Obtidos',
        'projeto': projeto,
        'nuvem': os.path.join(settings.MEDIA_URL+ 'nuvens', filename),
    }, RequestContext(request, ))


def solicitar_csv(request, id):
    projeto = get_object_or_404(Projeto, pk=id)
    tweets = Tweet.objects.filter(termo__projeto_id=projeto.pk)
    filename = 'tags-%d' % projeto.pk
    th = Thread(target=generate_tags_file, args=(tweets, filename,))
    th.start()
    Processamento.objects.create(termo=projeto.termo_set.all()[0], dt=datetime.datetime.now(), tipo=PROC_TAGS)
    messages.success(request, 'A geração do csv foi iniciada. Dê um refresh até que apareça o botão de Download CSV')
    return redirect(reverse('admin:index'))