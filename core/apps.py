import csv
import os
import zipfile
import shlex
import logging
from threading import Thread

from django.apps import AppConfig

from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse
from django.contrib import messages

from core import intdef
from core.models import *


class CoreConfig(AppConfig):
    name = 'core'


def update_stats_action(description=u"Recalcular estatísticas"):
    def recalcular(modeladmin, request, queryset):
        alterados = 0
        for projeto in queryset:
            for termo in projeto.termo_set.all():
                termo.last_count = termo.tot_twits
                termo.save()
            alterados += 1
        messages.info(request, u'%d termos alterados' % alterados)

    recalcular.short_description = description
    return recalcular

def detach_action(description=u"Desassociar tweet do Projeto"):
    def detach(modeladmin, request, queryset):
        alterados = 0
        for tweet in queryset:
            tweet.termo_id = None
            tweet.save()
            alterados += 1
        messages.info(request, u'%d tweets retirados do projeto' % alterados)

    detach.short_description = description
    return detach


def export_tags_action(description=u"Exportar CSV Completo"):
    def export_tags(modeladmin, request, queryset):
        generate_tags_file(queryset, 'admin')
        with open(os.path.join(settings.MEDIA_ROOT, 'full-admin.zip'), 'rb') as f:
            file_data = f.read()
        response = HttpResponse(file_data, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename=tags_%s.zip' % modeladmin.opts.db_table
        return response

    export_tags.short_description = description
    return export_tags


def generate_tags_file(queryset, project_id):
    path = settings.MEDIA_ROOT
    filename_log = os.path.join(path,'tags.log')
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(filename_log),
            logging.StreamHandler()
        ]
    )
    logging.info('Rotina iniciada')
    try:
        tags_filename = os.path.join(path, 'tags-%s.csv' % project_id)
        csv_filename = os.path.join(path, 'full-%s.csv' % project_id)
        tagsfile = open(tags_filename, 'w')
        csvfile = open(csv_filename, 'w')
        writer_tags = csv.writer(tagsfile)
        writer_tags.writerow(['id_str', 'from_user', 'text', 'created_at',
                         'time', 'geo_coordinates', 'user_lang', 'in_reply_to_user_id', 'in_reply_to_screen_name',
                         'from_user_id_str', 'in_reply_to_status_id_str', 'source', 'profile_image_url',
                         'user_followers_count', 'user_friends_count', 'user_location',
                         'status_url', 'entities_str'])

        writer_full = csv.writer(csvfile)
        writer_full.writerow(['id_str', 'from_user', 'text', 'created_at', 'user_lang', 'from_user_id_str',
                              'favorites', 'retweets', 'retweet_id', 'url'])

        num_lines = 0
        for obj in queryset:
            if obj.text[0:1] != 'RT':
                line = ["%s" % obj.twit_id, obj.user.username, "%s" % obj.text.replace('"',''), obj.created_time.strftime("%a %b %d %H:%M:%S %z %Y"),
                        obj.created_time.strftime("%d/%m/%Y %H:%M:%S"), '', obj.language, obj.user.twit_id, '',
                        '', '', '', '',
                        obj.user.followers, 0, obj.user.location,
                        '', '{"hashtags":[],"symbols":[],"user_mentions":[],"urls":[]}']
                writer_tags.writerow(line)
                num_lines += 1
                for retweet in obj.retweet_set.filter(retweet_id__isnull=False):
                    line = [retweet.retweet_id, retweet.user.username, 'RT %s' % obj.text.replace('"', ''),
                            obj.created_time.strftime("%a %b %d %H:%M:%S %z %Y"),
                            obj.created_time.strftime("%d/%m/%Y %H:%M:%S"), '', obj.language, '', '',
                            '', '', '', '',
                            obj.user.followers, 0, obj.user.location,
                            '', '{"hashtags":[],"symbols":[],"user_mentions":[],"urls":[]}']
                    writer_tags.writerow(line)
                    num_lines += 1

            writer_full.writerow([
                obj.twit_id, obj.user.username, "%s" % obj.text.replace('"', ''),
                obj.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                obj.language, "%s" % obj.user.twit_id, obj.favorites, obj.retweets, "%s" % obj.retwit_id,
                "https://twitter.com/i/web/status/%s" % obj.twit_id
            ])
        csvfile.close()
        tagsfile.close()
        logging.info('Linhas exportadas:%d' % num_lines)

        path_zip = os.path.join(path, 'tags-%s.zip' % project_id)
        with zipfile.ZipFile(path_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zip:
            zip.write(os.path.join(path, 'tags-%s.csv' % project_id), 'tags-%s.csv' % project_id)


        path_zip = os.path.join(path, 'full-%s.zip' % project_id)
        with zipfile.ZipFile(path_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zip:
            zip.write(os.path.join(path, 'full-%s.csv' % project_id), 'full-%s.csv' % project_id)

        logging.info('Zip %s criado com sucesso' % path_zip)
        os.remove(os.path.join(path, 'tags-%s.csv' % project_id))
        os.remove(os.path.join(path, 'full-%s.csv' % project_id))
        if intdef(project_id,0) != 0:
            termo = Termo.objects.filter(projeto_id=project_id).first()
            Processamento.objects.create(termo=termo, dt=timezone.now(), tipo=PROC_TAGS)

    except:
        logging.error('Erro fatal', exc_info=True)


def export_extra_action(description=u"Exportar CSV com retweets"):

    def export_extra(modeladmin, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=full%s.csv' % modeladmin.opts.db_table

        writer = csv.writer(response)
        writer.writerow(['tweet_id', 'text', 'user', 'user_id', 'created_time',
                         'retweets', 'favorites', 'tweet_original'])
        for obj in queryset:
            line = [obj.twit_id, obj.text, obj.user, obj.user.twit_id,
                    obj.created_time.strftime("%a %b %d %H:%M:%S %z %Y"),
                    obj.retweets, obj.favorites, ]
            writer.writerow(line)
            for retweet in obj.retweet_set.filter(retweet_id__isnull=False):
                line = [retweet.retweet_id, retweet.tweet.text, retweet.user, retweet.user.twit_id,
                        obj.created_time.strftime("%a %b %d %H:%M:%S %z %Y"), 0, 0, retweet.tweet.twit_id]
                writer.writerow(line)
        return response
    export_extra.short_description = description
    return export_extra


def busca_local(id):
    termo = Termo.objects.get(id=id)
    termos_busca = termo.busca.lower()
    proc = Processamento.objects.filter(termo=termo, tipo=termo.tipo_busca).first()
    if not proc:
        proc = Processamento.objects.create(termo=termo, dt=timezone.now(), tipo=termo.tipo_busca)
    maior = proc.twit_id or '0'

    lista_busca = list(map(lambda x: x.lower(), shlex.split(termos_busca)))

    # Buscar em cada tweet da base se a descrição faz match com o termo selecionado e associa ao termo
    if termo.status == PROC_FILTROPROJ:
        dataset = Tweet.objects.filter(tweetinput__termo__projeto_id=termo.projeto_id)
    elif termo.dtinicio:
        dataset = Tweet.objects.filter(created_time__gte=termo.dtinicio)

    if termo.language:
        dataset = dataset.filter(language=termo.language)

    for tweet in dataset.filter(text__icontains=lista_busca[0]):
        if termo.tipo_busca == PROC_BUSCAGLOBAL:
            achou = True
        elif termo.status == PROC_FILTROPROJ and \
                tweet.tweetinput_set.filter(termo__projeto_id=termo.projeto_id).count() > 0:
            achou = True
        else:
            achou = False

        if achou and len(lista_busca) > 1:
            texto = tweet.text.lower()
            for item in lista_busca:
                if item[0] == '-':
                    if item[1:] in texto:
                        achou = False
                        break
                else:
                    if item not in texto:
                        achou = False
                        break

        if achou:
            if not TweetInput.objects.filter(tweet=tweet, termo=termo):
                TweetInput.objects.create(tweet=tweet, termo=termo, processamento=proc)
                if tweet.twit_id > maior:
                    maior = tweet.twit_id

    termo.status = 'C'
    termo.save()
    proc.twit_id = maior
    proc.save()
    return
