import os
import csv
import random
from threading import Thread
from collections import Counter

from django.db import connection
from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, render_to_response, redirect

# Create your views here.

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
import requests
from django.template import RequestContext
from django.urls import reverse
from wordcloud import WordCloud

from core.apps import generate_tags_file, check_dir
from core.models import Projeto, Tweet, Processamento, PROC_TAGS, PROC_IMPORTACAO, TweetUser, Retweet
from twitsearch.settings import BASE_DIR
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sb

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


def stats(request, id):
    projeto = get_object_or_404(Projeto, pk=id)
    palavras = projeto.most_common()
    top_tweets = Tweet.objects.filter(termo__projeto_id=id).order_by('-favorites')[:3]
    proc_tags = Processamento.objects.filter(termo=projeto.termo_set.all()[0], tipo=PROC_TAGS)
    proc_importacao = Processamento.objects.filter(termo__projeto=projeto, tipo=PROC_IMPORTACAO)

    alcance = 0
    path = os.path.join(settings.MEDIA_ROOT, 'csv')
    check_dir(path)
    filename_csv = 'users-%s.csv' % id
    csvfile = open(os.path.join(path, filename_csv), 'w')
    writer = csv.writer(csvfile)
    writer.writerow(['username','favorites','retweets','count'])
    with connection.cursor() as cursor:
        cursor.execute('select u.username, max(t.favorites) fav, max(t.retweets) rt, count(*) count'
                       '  from core_tweet t, core_termo p, core_tweetuser u'
                       ' where p.projeto_id = %s and t.termo_id = p.id and t.user_id = u.twit_id'
                       '   and created_time between p.dtinicio and p.dtfinal + 1'
                       '       group by t.user_id order by fav desc', [id])
        for rec in cursor.fetchall():
            writer.writerow(rec)
            alcance += max(int(rec[1]), int(rec[2]))
    csvfile.close()

    dataset = []
    dias = Counter()
    with connection.cursor() as cursor:
        cursor.execute("select DATE_FORMAT(created_time, '%%Y%%m%%d') as dia, "
                       "       DATE_FORMAT(created_time, '%%H') as hora, count(*) as total"
                       "  from core_tweet t, core_termo p" 
                       " where p.projeto_id = %s and t.termo_id = p.id " 
                       "   and created_time between p.dtinicio and p.dtfinal + 1"
                       "       group by dia, hora order by dia, hora",
                       [id])
        for rec in cursor.fetchall():
            dataset.append(rec)
            dias[rec[0]] += rec[2]

    dias_sorted = sorted([dia for dia, _ in dias.most_common()])

    if len(dias_sorted) > 30:
        # Achar a melhor faixa para mostrar o heatmap
        dias_np = np.array([total for _, total in dias.most_common()])
        media = np.average(dias_np)
        base = media - np.std(dias_np)
        limite_inferior = np.max(dias_np)
        idx_inicial = 0
        for dia in dias_sorted:
            if dias[dia] >= base:
                if idx_inicial + 29 > len(dias_sorted):
                    idx_inicial = len(dias_sorted) - 29
                break
            idx_inicial += 1
        dias_sorted = dias_sorted[idx_inicial:]
    else:
        inicio = 0

    dias_valores = []
    for dia in dias_sorted:
        dias_valores.append(dias[ dia ])

    # heatmap = np.empty((24, len(dias_sorted)))
    # heatmap[:] = 0
    # dia = 0
    # for rec in dataset:
    #     if rec[0] in dias:
    #         hora = int(rec[1])
    #         heatmap[hora, dias_sorted.index(rec[0])] = int(rec[2])
    #
    # # Plot the heatmap, customize and label the ticks
    fig = plt.figure()
    ax = fig.add_subplot(111)
    # # im = ax.imshow(heatmap, interpolation='nearest')
    # sb.heatmap(heatmap)
    days = np.array(range(0, len(dias_sorted), 10))
    # ax.set_xticks(days)
    # ax.set_xticklabels(['%s' % day[-2:] for day in dias_sorted])
    # ax.set_xlabel('Dias')
    # ax.set_title('Tweets por faixa de horário')
    #
    # # Monta Eixo Y com as horas
    # horas = np.array(range(0, 23))
    # ax.set_yticks(horas)
    # ax.set_ylabel('Horas do dia')
    # ax.set_yticklabels(['%s' % hora for hora in horas])
    #
    # filename = 'heatmap-%s.png' % id
    # path = os.path.join(settings.MEDIA_ROOT, 'heatmap')
    # # testa se os diretorios existem senao cria
    # check_dir(path)
    #
    # plt.savefig(os.path.join(path, filename), bbox_inches='tight')
    # plt.xlim(1.3, 4.0)
    # plt.show()

    # grafico de barra
    path_bar = os.path.join(settings.MEDIA_ROOT, 'graficos')
    check_dir(path_bar)
    filename_bar = 'bar-%s.png' % id

    #plt.bar(dias_sorted, dias_valores, color='red')
    sb.barplot(dias_sorted, dias_valores)

    plt.ylabel('Total de tweets')
    plt.xlabel('Dias do mês')
    ax.set_xticks(days)
    plt.xticks(days, ['%s' % day[-2:] for day in dias_sorted])
    plt.title('Total de tweets por dia')
    plt.savefig(os.path.join(path_bar, filename_bar))
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
        'alcance' : alcance,
        'download': exportacao,
        #'heatmap': os.path.join(settings.MEDIA_URL, 'heatmap', filename),
        'bar': os.path.join(settings.MEDIA_URL, 'graficos', filename_bar ),
        'csv': filename_csv,

    }, RequestContext(request, ))


def nuvem(request, id):
    projeto = get_object_or_404(Projeto, pk=id)
    cloud = WordCloud(width=1200, height=800, max_words=60, scale=2, background_color='white')
    palavras = dict(projeto.most_common())
    cloud.generate_from_frequencies(palavras)
    path = os.path.join(BASE_DIR, 'media', 'nuvens')

    if not os.path.exists(path):
        if not os.path.exists(settings.MEDIA_ROOT):
            os.mkdir(settings.MEDIA_ROOT)  # dir media
        os.mkdir(os.path.join(settings.MEDIA_ROOT, 'nuvens'))  # path

    filename = 'nuvem-%s.png' % projeto.pk
    cloud.to_file(os.path.join(path, filename))

    return render_to_response('core/nuvem.html', {
        'title': u'Estatísticas dos Twitters Obtidos',
        'projeto': projeto,
        'nuvem': os.path.join(settings.MEDIA_URL + 'nuvens', filename),
    }, RequestContext(request, ))


def solicitar_csv(request, id):
    get_object_or_404(Projeto, pk=id)
    tweets = Tweet.objects.filter(termo__projeto_id=id)
    th = Thread(target=generate_tags_file, args=(tweets, id,))
    th.start()
    messages.success(request,
                     'A geração do csv foi iniciada. Atualize essa página (teclando F5) '
                     'até que apareça o botão de Download CSV')
    return redirect(reverse('core_projeto_stats', kwargs={'id': id}))


def create_graph(request, id_projeto):
    get_object_or_404(Projeto, pk=id_projeto)
    g = nx.DiGraph()

    # A rede é formada pelos usuários e não pelos tweets.
    tweets = Tweet.objects.filter(termo__projeto_id__exact=id_projeto).order_by('-retweets')[:200]
    for tweet in tweets:
        g.add_node(tweet.user.name, )
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

def gerar_gephi(request, id_projeto):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="gephi.csv"'
    csv_file = csv.writer(response)
    csv_file.writerow(['Tweet', 'Retweet'])
    dataset = list(Retweet.objects.filter(tweet__termo__projeto_id=id_projeto).select_related().values_list('tweet__user__username', 'user__username'))
    for data in dataset:
        csv_file.writerow(data)

    return response

# def use_seaborn(request):
#     import seaborn as sb
#     data = np.random.rand(4,6)
#     heat_map = sb.heatmap(data)
#     plt.show()
