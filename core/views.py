import os
import random
from threading import Thread

from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, render_to_response, redirect

# Create your views here.

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
import requests
from django.template import RequestContext
from django.urls import reverse
from wordcloud import WordCloud

from core.apps import generate_tags_file
from core.models import Projeto, Tweet, Processamento, PROC_TAGS, PROC_IMPORTACAO, TweetUser, Retweet
from twitsearch.settings import BASE_DIR
import networkx as nx
import matplotlib.pyplot as plt


def index(request):
    return render(request, 'home.html', context={'hello': 'world'})


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

import numpy as np
import numpy.random
import matplotlib.pyplot as plt

def stats(request, id):
    projeto = get_object_or_404(Projeto, pk=id)
    palavras = projeto.most_common()
    top_tweets = Tweet.objects.filter(termo__projeto_id=id).order_by('-favorites')[:3]
    proc_tags = Processamento.objects.filter(termo=projeto.termo_set.all()[0], tipo=PROC_TAGS)
    proc_importacao = Processamento.objects.filter(termo__projeto=projeto, tipo=PROC_IMPORTACAO)

    # # Generate some test data
    # x = list([1,7,7,8,9,5,4])
    # y = list([1,2,3,1212,31,4,2])
    #
    # heatmap, xedges, yedges = np.histogram2d(x, y, bins=50)
    # extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
    #
    # plt.clf()
    # plt.imshow(heatmap.T, extent=extent)
    # plt.show()

    import numpy as np
    import matplotlib.pyplot as plt

    # In our heatmap, nan will mean "no such date", e.g. 31 June
    # hora, dia, twitte
    data = [(10, 3, '1'), (11, 2,'2'), (11, 4,'2121212'), (11, 3, '2121212'), (20, 15, '12'),(0, 11, '1213123123123123')]

    heatmap = np.empty((31, 23))
    heatmap[:] = np.nan

    for hour, day, T in data:
        # NumPy arrays are zero-indexed; days and months are not!
        heatmap[day -1 , hour] = T

    # Plot the heatmap, customize and label the ticks
    fig = plt.figure()
    ax = fig.add_subplot(111)
    im = ax.imshow(heatmap, interpolation='nearest')
    #ax.set_yticks(range(12))
    #ax.set_yticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            #            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    days = np.array(range(0, 31, 2))
    ax.set_yticks(days)
    ax.set_yticklabels(['{:d}'.format(day + 1) for day in days])
    ax.set_ylabel('Dias do mês')
    ax.set_title('Tweets por faixa de horário')

    horas = np.array(range(0, 23, 2))
    ax.set_xticks(horas)
    ax.set_xlabel('Horas do dia')

    # # Add a colour bar along the bottom and label it
    # cbar = fig.colorbar(ax=ax, mappable=im, orientation='horizontal')
    # cbar.set_label('Twi')

    plt.show()


    try:
        if proc_tags[0].pk > proc_importacao[0].pk:
            exportacao = 'tags-%d.zip' % projeto.id
        else:
            exportacao = None
    except:
        exportacao = None

    return render(request, 'core/stats.html', {
        'title': u'Estatísticas do Projeto',
        'projeto': projeto,
        'palavras': palavras,
        'top_tweets': top_tweets,
        'download': exportacao,
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
    get_object_or_404(Projeto, pk=id)
    tweets = Tweet.objects.filter(termo__projeto_id=id)
    th = Thread(target=generate_tags_file, args=(tweets, id,))
    th.start()
    messages.success(request, 'A geração do csv foi iniciada. Atualize essa página (teclando F5) até que apareça o botão de Download CSV')
    return redirect(reverse('core_projeto_stats', kwargs={'id': id}))


def create_graph(request, id_projeto):
    get_object_or_404(Projeto, pk=id_projeto)
    g = nx.DiGraph()

    # A rede é formada pelos usuários e não pelos tweets.
    tweets = Tweet.objects.filter(termo__projeto_id__exact=id_projeto).order_by('-retweets')[:200]
    for tweet in tweets:
        g.add_node(tweet.user.name,)
        for retweet in tweet.retweet_set.all():
            g.add_edge(tweet.user.name, retweet.user.name)

    pos = nx.spring_layout(g)  # gerando posicoes aleatorias

    for p in pos.items():
        blue = random.randint(0, 255)
        green = random.randint(0, 255)
        red = random.randint(0, 255)
        alpha = random.randint(0, 255)
        node = p[0]
        info = list(p[1])
        g.nodes[node]['viz'] = {'size': 100,
                                'color': {'b': '%s' % blue, 'g': '%s' % green, 'r': '%s' % red, 'a': '%s' % alpha},
                                'position': {
                                    'x': info[0],
                                    'y': info[1]
                                }
                                }
    print(nx.info(g))
    print('Density: %s' % nx.density(g))

    # Gerando o arquivo gexf para ser utilizado no sigma
    # TODO: Habilitar botão no template para que o usuário possa fazer o download do GEXF para outros programas
    filename = 'grafo-%s.gexf' % id_projeto
    path = os.path.join(settings.MEDIA_ROOT, 'grafos')
    if not os.path.exists(path):
        if not os.path.exists(settings.MEDIA_ROOT):
            os.mkdir(settings.MEDIA_ROOT)
        os.mkdir(os.path.join(settings.MEDIA_ROOT, 'grafos'))

    nx.write_gexf(g, os.path.join(settings.MEDIA_ROOT, 'grafos', filename))  # exportando grafo para gexf

    # geração de imagem
    # nx.draw(g, with_labels=True, node_size=100, font_size=5, )  # desenha o grafo
    # plt.savefig(os.path.join(path, filename))
    # plt.show()

    return render(request, 'core/grafo.html', {
        'grafo': os.path.join(settings.MEDIA_URL, 'grafos', filename)
    })
