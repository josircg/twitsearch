# -*- coding: utf-8 -*-
import json
import pytz
import time
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand

from twitsearch.local import get_api

import tweepy

from twitsearch.settings import TIME_ZONE
from core.models import Termo, Processamento


def save_result(data, processo):
    data['process'] = processo
    filename = 'data/%s.json' % data['id']
    arquivo = open(filename, 'w')
    json.dump(data, arquivo)
    arquivo.close()
    print('%s saved' % filename)


class SimpleListener(tweepy.StreamListener):

    def __init__(self):
        super(SimpleListener, self).__init__()
        self.checkpoint = 20
        self.processo = None
        self.dtfinal = None

    def on_data(self, status):
        # code to run each time you receive some data (direct message, delete, profile update, status,...)
        data = json.loads(status)
        if 'disconnect' in data:
            if self.on_disconnect(data['disconnect']) is False:
                return False
        elif 'warning' in data:
            if self.on_warning(data['warning']) is False:
                print(data['warning'])
                return False

        save_result(data, self.processo.id)

        return self.checkpoint > 0

    def on_error(self, status_code):
        # code to run each time an error is received
        if status_code == 420:
            return False
        else:
            return True


def processa_item_unico(twitid, termo):
    agora = datetime.now(pytz.timezone(TIME_ZONE))
    termo = Termo.objects.get(id=termo)
    listener = SimpleListener()
    listener.processo = Processamento.objects.create(termo=termo, dt=agora)
    listener.dtfinal = termo.dtfinal
    api = get_api()
    tweepy_stream = tweepy.Stream(auth=api.auth, listener=listener)
    tweepy_stream.filter(track=[termo.busca], is_async=True)
    print('Twit %s importado' % twitid)


class Command(BaseCommand):
    label = 'Grab Twitters'

    def add_arguments(self, parser):
        parser.add_argument('--twit', type=str, help='Twitter ID')
        parser.add_argument('--proc', type=str, help='Processo')

    def handle(self, *args, **options):
        agora = timezone.now()
        if 'twit' in options and options['twit']:
            processa_item_unico(options['twit'], options['termo'])
            return

        termo = Termo.objects.filter(status='A').order_by('ult_processamento').first()
        if not termo:
            print('Nenhum termo para processar')
            return

        ultimo = termo.ult_tweet

        # Se o último processamento foi hoje, a busca é feita via stream para obter novos tweets
        # Se foi anterior que hoje ou nula, busca-se primeiro termos antigos
        if termo.ult_processamento:
            ult_processamento = max(termo.ult_processamento + timedelta(days=1), agora - timedelta(days=7))
        else:
            ult_processamento = max(termo.dtinicio, agora - timedelta(days=7))

        if ult_processamento.date() < agora.date():
            processo = Processamento.objects.create(termo=termo, dt=agora)
            Termo.objects.filter(id=termo.id).update(status='P', ult_processamento=agora.date())
            print('Search %s %d %d' % (termo.busca, processo.id, termo.id))
            api = get_api()
            termo_busca = termo.busca
            if ultimo:
                termo_busca += ' since_id:%d' % ultimo
            # results = tweepy.Cursor(api.search, q=termo.busca+extra_filter, since_id=ultimo,
            #                         tweet_mode='extended', rpp=100, page=10).items()
            results = tweepy.Cursor(api.search, q=termo.busca, tweet_mode='extended').items()
            status_proc = ''
            try:
                for status in results:
                    save_result(status._json, processo.id)
                    if status.id > ultimo:
                        ultimo = status.id
                    status_proc = Termo.objects.get(id=termo.id).status
                    if status_proc == 'I':
                        print('Processo interrompido')
                        break
            except Exception as e:
                print('API Timeout: %s' % e.__str__())
        else:
            listener = SimpleListener()
            listener.processo = Processamento.objects.create(termo=termo, dt=agora)
            listener.dtfinal = termo.dtfinal
            Termo.objects.filter(id=termo.id).update(status='P')
            print('Stream %d' % listener.processo.id)
            api = get_api()
            status_proc = 'A'
            termo_busca = termo.busca
            if ultimo:
                termo_busca += ' since_id:%d' % ultimo
            tweepy_stream = tweepy.Stream(auth=api.auth, listener=listener)
            tweepy_stream.filter(track=[termo_busca], is_async=True)
            while listener.checkpoint > 0 and listener.dtfinal > agora and status_proc == 'P':
                time.sleep(60)
                agora = datetime.now(pytz.timezone(TIME_ZONE))
                status_proc = Termo.objects.get(id=termo.id).status
                listener.checkpoint -= 5
                print('Checkpoint %d' % listener.checkpoint)

            # se saiu do loop pois ficou muito tempo sem encontrar tweets, mantem a busca ativa
            tweepy_stream.disconnect()
            if listener.dtfinal > agora:
                Termo.objects.filter(id=termo.id).update(status='A', ult_processamento=agora)
            else:
                Termo.objects.filter(id=termo.id).update(status='C', ult_processamento=agora)

        ult_processamento = min(ult_processamento + timedelta(days=1), agora)
        if termo.dtfinal < ult_processamento:
            status_proc = 'C'
        else:
            status_proc = 'A' if status_proc != 'I' else 'I'

        Termo.objects.filter(id=termo.id).update(status=status_proc,
                                                 ult_processamento=ult_processamento,
                                                 ult_tweet=ultimo)
        print('Processamento concluído')
