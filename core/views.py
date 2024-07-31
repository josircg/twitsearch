import os
import csv
import random
import pytz
import traceback

from datetime import datetime
from threading import Thread
from PIL import Image

from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, render, redirect

from django.http import HttpResponse
from django.template import RequestContext
from django.urls import reverse
from wordcloud import WordCloud

from core import check_dir, intdef, find_urls
from core.actions import generate_tags_file, busca_local, import_xlsx, import_list
from core.forms import ImportForm
from core.models import *
from core.management.commands.remove_json import remove_json
from twitsearch.settings import BASE_DIR, TIME_ZONE
import networkx as nx
import numpy as np

from plotly.offline import plot
from plotly import graph_objs


def index(request):
    return render(request, 'home.html', context={'hello': 'world'})


def visao(request):
    return


def stats(request, project_id):
    agora = timezone.now()
    projeto = get_object_or_404(Projeto, pk=project_id)
    termo_base = projeto.termo_set.all().first()
    palavras = projeto.most_common()
    top_tweets = Tweet.objects.filter(tweetinput__termo__projeto_id=project_id).order_by('-favorites')[:5]

    proc_tags = Processamento.objects.filter(termo__projeto=projeto, tipo=PROC_TAGS).last()
    proc_importacao = Processamento.objects.filter(
        termo__projeto=projeto,
        tipo__in=(PROC_IMPORTACAO, PROC_IMPORTUSER, PROC_PREMIUM, PROC_MATCH, PROC_BUSCAGLOBAL)).last()
    if not proc_importacao:
        proc_importacao = Processamento.objects.create(tipo=PROC_MATCH, termo=termo_base,
                                                       dt=agora, status=Processamento.CONCLUIDO)

    filename_csv = 'users-%s.csv' % project_id

    if not proc_tags or proc_tags.dt <= proc_importacao.dt:
        alcance = 0
        tot_registros = 0
        path = os.path.join(settings.MEDIA_ROOT, 'csv')
        check_dir(path)
        csvfile = open(os.path.join(path, filename_csv), 'w')
        writer = csv.writer(csvfile)
        writer.writerow(['username', 'favorites', 'retweets', 'count'])
        with connection.cursor() as cursor:
            cursor.execute('select u.twit_id, u.username, max(t.favorites) fav, max(t.retweets) rt, count(*) count'
                           '  from core_termo p, core_tweetinput  i, core_tweet t, core_tweetuser u'
                           ' where p.projeto_id = %s and p.id = i.termo_id and i.tweet_id = t.twit_id'
                           '   and t.user_id = u.twit_id'
                           '   and t.created_time between p.dtinicio and p.dtfinal + 1'
                           '       group by u.twit_id, u.username order by fav desc', [project_id])
            for rec in cursor.fetchall():
                writer.writerow(rec)
                alcance += max(int(rec[2]), int(rec[3]), int(rec[4]))
                tot_registros += 1
        csvfile.close()
        projeto.alcance = alcance
        projeto.save()
        proc_tags, created = Processamento.objects.get_or_create(
                                termo__projeto=projeto, tipo=PROC_TAGS,
                                defaults={'dt': agora,
                                          'status': Processamento.AGENDADO,
                                          'tot_registros': tot_registros})
        if not created:
            proc_tags.dt = agora
            proc_tags.status = Processamento.AGENDADO
            proc_tags.tot_registros = tot_registros
            proc_tags.save()

    dataset = []
    dias = Counter()
    with connection.cursor() as cursor:
        cursor.execute("select DATE_FORMAT(created_time, '%%Y%%m%%d') as dia, "
                       "       DATE_FORMAT(created_time, '%%H') as hora, count(*) as total"
                       "  from core_termo p, core_tweetinput i, core_tweet t" 
                       " where p.projeto_id = %s and p.id = i.termo_id and i.tweet_id = t.twit_id" 
                       "   and created_time between ifnull(p.dtinicio,t.created_time) and p.dtfinal + 1"
                       "       group by dia, hora order by dia, hora",
                       [project_id])
        for rec in cursor.fetchall():
            dataset.append(rec)
            dias[rec[0]] += rec[2]

    dias_sorted = sorted([dia for dia, _ in dias.most_common()])

    # Achar a melhor faixa para mostrar o heatmap
    '''
    if len(dias_sorted) > 30:
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
    '''

    dias_valores = []
    for dia in dias_sorted:
        dias_valores.append(dias[dia])

    '''
    heatmap = np.empty((24, len(dias_sorted)))
    heatmap[:] = 0
    for rec in dataset:
        if rec[0] in dias_sorted:
            hora = int(rec[1])
            heatmap[hora, dias_sorted.index(rec[0])] = int(rec[2])

    fig = graph_objs.Figure(data=graph_objs.Heatmap(
        z=heatmap,
        x=[datetime.strftime(datetime.strptime(data, '%Y%m%d'), '%d/%m/%Y') for data in dias_sorted],
        colorscale='Viridis'
    ))
    fig.update_layout(
        title='Tweets por faixa de horário',
        xaxis_nticks=36,
        xaxis=graph_objs.layout.XAxis(
            title=graph_objs.layout.xaxis.Title(
                text='Dias'
            )
        ),
        yaxis=graph_objs.layout.YAxis(
            title=graph_objs.layout.yaxis.Title(
                text="Horas do dia",
                # font=dict(
                #     family="Courier New, monospace",
                #     size=18,
                #     color="#7f7f7f"
                # )
            )
        )
    )
    heatmap_div = plot(fig, output_type='div')
    '''
    heatmap_div = ''

    dias_formatted = []
    for dia in dias_sorted:
        date = datetime.strptime(dia, '%Y%m%d')
        dias_formatted.append(datetime.strftime(date, '%d/%m/%Y'))

    fig2 = graph_objs.Figure(graph_objs.Bar(
        x=dias_formatted,
        y=dias_valores
    ))

    fig2.update_layout(title='Tweets por dia',
        xaxis_nticks=36,
        xaxis=graph_objs.layout.XAxis(
                title=graph_objs.layout.xaxis.Title(
                    text='Dias do mês'
            )
        ),
        yaxis=graph_objs.layout.YAxis(
            title=graph_objs.layout.yaxis.Title(
                text="Total de Tweets",
                )
        )
    )
    grafico_div = plot(fig2, output_type='div')

    if proc_tags.status == Processamento.CONCLUIDO:
        csv_tags = 'tags-%d.zip' % projeto.id
        csv_completo = 'full-%d.zip' % projeto.id
    else:
        csv_completo = None
        csv_tags = None

    return render(request, 'core/stats.html', {
        'title': u'Estatísticas do Projeto',
        'projeto': projeto,
        'palavras': palavras,
        'top_tweets': top_tweets,
        'csv_tags': csv_tags,
        'csv_completo': csv_completo,
        'heatmap_div': heatmap_div,
        'grafico_div':grafico_div,
        # 'heatmap': os.path.join(settings.MEDIA_URL, 'heatmap', filename),
        # 'bar': os.path.join(settings.MEDIA_URL, 'graficos', filename_bar ),
        'csv': filename_csv })


def most_used_urls(request, id):
    # Para cada tweet do projeto (sem considerar os retweets), montar um Counter com as URLs encontradas
    projeto = get_object_or_404(Projeto, pk=id)
    url_counter = Counter()
    for tweet in Tweet.objects.filter(tweetinput__termo__projeto=projeto):
        urls = find_urls(tweet.text)
        for url in urls:
            url_counter[url] += 1
    return url_counter.most_common()


def backup_json(request, project_id):
    # Agenda processo de backup para o projeto
    agora = datetime.now(pytz.timezone(TIME_ZONE))
    termo = Termo.objects.filter(projeto_id=project_id).order_by('id').first()
    # Verifica primeiro se já não existe um backup agendado
    proc = Processamento.objects.filter(termo=termo, tipo=PROC_BACKUP).first()
    if proc:
        if proc.status == Processamento.CONCLUIDO:
            messages.success(request, 'O backup já foi concluído. Verifique no S3')
        else:
            messages.warning(request, 'Backup não concluído')
    else:
        Processamento.objects.create(dt=agora, termo=termo, tipo=PROC_BACKUP, status=Processamento.AGENDADO)
        messages.success(request, 'A montagem do backup foi iniciada. '
                                  'Verifique se o processo foi concluído diretamente no S3'
                                  'ou clicando no botão de Backup novamente')
    return redirect(reverse('admin:core_projeto_change', args=[project_id]))


def exclui_json(request, project_id):
    projeto = get_object_or_404(Projeto, pk=project_id)
    proc = Processamento.objects.filter(termo__projeto=projeto, tipo=PROC_BACKUP,
                                        status=Processamento.CONCLUIDO)
    if proc:
        remove_json(projeto)
    else:
        messages.error(request, 'O backup deve ser realizado antes da exclusão')

    return redirect(reverse('admin:core_projeto_change', args=[project_id]))


def nuvem(request, project_id, modelo=None):
    projeto = get_object_or_404(Projeto, pk=project_id)

    path = os.path.join(BASE_DIR, 'media', 'nuvens')
    if not os.path.exists(path):
        if not os.path.exists(settings.MEDIA_ROOT):
            os.mkdir(settings.MEDIA_ROOT)  # dir media
        os.mkdir(os.path.join(settings.MEDIA_ROOT, 'nuvens'))  # path

    # modelo espera nulo (modelo padrão), 1 ou 2 da view.
    modelo = intdef(modelo, 0)
    palavras = None
    mask = None
    csv_lido = False
    debug = ''
    if modelo != 0:
        filename = os.path.join(path, f'nuvem-{projeto.id}.csv')
        if not os.path.exists(filename):
            modelo = 0
            debug = f'csv não encontrado {filename}'

    if modelo != 0:
        with open(os.path.join(path, filename), 'r') as csvfile:
            reader = csv.reader(csvfile)
            next(reader, None)
            palavras = dict((rows[0], int(rows[1])) for rows in reader)
        csv_lido = True

        modelo_filename = os.path.join(BASE_DIR, 'templates', 'nuvem', f'modelo{modelo}.png')
        try:
            image = Image.open(modelo_filename)
            mask = np.array(image)
        except Exception as e:
            mask = None
            palavras = None
            debug = e.__str__()

    if not palavras:
        palavras = dict(projeto.most_common())

    if len(palavras) == 0:
        messages.error(request,'Nenhuma palavra encontrada para a montagem da nuvem')
        return redirect(reverse('admin:core_projeto_change', args=project_id))

    if projeto.stopwords:
        for word in projeto.stopwords.split(','):
            stopword = word.lower().strip()
            if stopword in palavras:
                del palavras[stopword]

    # Grava o CSV caso ele não tenha sido lido
    if not csv_lido:
        filename = os.path.join(path, f'nuvem-{projeto.id}.csv')
        with open(filename, 'w') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['word', 'frequency', ])
            writer.writerows(palavras.items())

    if modelo == 2:
        font_path = os.path.join(BASE_DIR, 'templates', 'nuvem', 'Comfortaa Bold.ttf')
    else:
        font_path = None

    cloud = WordCloud(width=1200, height=800, max_words=60, scale=2, background_color='white', mask=mask,
                      font_path=font_path)
    cloud.generate_from_frequencies(palavras)

    # Grava a imagem da nuvem
    filename = f'nuvem-{projeto.pk}-{modelo}.png'
    cloud.to_file(os.path.join(path, filename))

    return render(request, 'core/nuvem.html', {
        'title': u'Nuvem de Palavras dos tweets obtidos',
        'projeto': projeto,
        'nuvem': os.path.join(settings.MEDIA_URL + 'nuvens', filename),
        'modelo': modelo + 1 if modelo < 2 else 0,
        'debug': debug})


def solicitar_csv(request, project_id):
    get_object_or_404(Projeto, pk=project_id)
    tweets = Tweet.objects.filter(tweetinput__termo__projeto_id=project_id)
    th = Thread(target=generate_tags_file, args=(tweets, project_id,))
    th.start()
    messages.success(request,
                     'A geração do csv foi iniciada. Atualize essa página (teclando F5) '
                     'até que apareça o botão de Download CSV')
    return redirect(reverse('core_projeto_stats', kwargs={'project_id': project_id}))


def create_graph(request, project_id):
    get_object_or_404(Projeto, pk=project_id)
    g = nx.DiGraph()

    # A rede é formada pelos usuários e não pelos tweets.
    tweets = Tweet.objects.filter(termo__projeto_id__exact=project_id).order_by('-retweets')[:200]
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
    filename = 'grafo-%s.gexf' % project_id
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


def gerar_gephi(request, project_id):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="gephi.csv"'
    csv_file = csv.writer(response)
    csv_file.writerow(['source', 'target'])
    for termo in Termo.objects.filter(projeto__id=project_id):
        for record in (Retweet.objects.filter(tweet__tweetinput__termo_id=termo).
                select_related().values_list('tweet__user__username', 'user__username')):
            csv_file.writerow(record[0], record[1])

    return response


def solicita_busca(request, termo_id):
    if Termo.objects.filter(id=termo_id, tipo_busca__in=(PROC_BUSCAGLOBAL, PROC_FILTROPROJ), status='A').count() == 0:
        messages.error(request, 'Utilize esta opção apenas para buscas locais')
        return redirect(reverse('admin:core_termo_change', args=[termo_id]))

    th = Thread(target=busca_local, args=(termo_id,))
    th.start()
    messages.success(request, 'A busca local foi iniciada. Aguarde que o status do Termo apareça como concluído.')
    return redirect(reverse('admin:core_termo_change', args=[termo_id]))


def get_source(request, tweet_id):
    filename = os.path.join(settings.BASE_DIR, 'data', 'cached', '%s.json2' % tweet_id)
    if not os.path.exists(filename):
        filename = os.path.join(settings.BASE_DIR, 'data', 'cached', '%s.json' % tweet_id)
        if not os.path.exists(filename):
            return HttpResponseNotFound("Arquivo não encontrado")

    with open(filename, 'r') as f:
        file_data = f.read()
    response = HttpResponse(file_data, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename=%s.json' % tweet_id
    return response



def importacao_arquivo(request):

    if request.method == 'POST':
        form = ImportForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = request.FILES.get('arquivo')
            termo = request.POST.get('termo')
            try:
                if arquivo:
                    if arquivo.name.lower().endswith('.txt'):
                        result = import_list(termo, arquivo)
                    else:
                        result = import_xlsx(termo, arquivo)
                    messages.info(request, result)
                else:
                    messages.error(request, 'Nenhum arquivo enviado. Tente utilizar outro navegador.')

            except Exception as e:
                message = ''.join(traceback.TracebackException.from_exception(e).format())
                print(message)
                # sendmail('Erro Importação Lattes', [settings.REPLY_TO_EMAIL], message=message)
                messages.error(request, 'Houve um erro durante a importação. Já estamos averiguando o problema')

            return redirect('importacao_arquivo')
    else:
        form = ImportForm()

    return render(request, 'core/import_tweets.html', {'form': form, })


# def use_seaborn(request):
#     import seaborn as sb
#     data = np.random.rand(4,6)
#     heat_map = sb.heatmap(data)
#     plt.show()
