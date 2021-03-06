# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import json
import pytz
import time
from datetime import datetime

from twitsearch.local import get_api

import tweepy

from twitsearch.settings import TIME_ZONE
from core.models import Termo, Processamento, convert_date


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
        self.checkpoint = 50
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


class Command(BaseCommand):
    label = 'Grab Twitters'

    def handle(self, *args, **options):
        agora = datetime.now(pytz.timezone(TIME_ZONE))
        termos = Termo.objects.filter(status='A', dtinicio__isnull=True).order_by('ult_processamento')
        if termos.count() > 0:
            termo = Termo.objects.get(pk=termos[0].id)
            listener = SimpleListener()
            listener.processo = Processamento.objects.create(termo=termo, dt=agora)
            listener.dtfinal = termo.dtfinal
            Termo.objects.filter(id=termo.id).update(status='P')
            print('Stream %d' % listener.processo.id)
            api = get_api()
            status = 'A'
            tweepy_stream = tweepy.Stream(auth=api.auth, listener=listener)
            tweepy_stream.filter(track=[termo.busca], is_async=True)
            while listener.checkpoint > 0 and listener.dtfinal > agora and status == 'P':
                time.sleep(180)
                agora = datetime.now(pytz.timezone(TIME_ZONE))
                status = Termo.objects.get(id=termo.id).status
                listener.checkpoint -= 5
                print('Checkpoint %d' % listener.checkpoint)

            # se saiu do loop pois ficou muito tempo sem encontrar tweets, mantem a busca ativa
            tweepy_stream.disconnect()
            if listener.dtfinal > agora:
                Termo.objects.filter(id=termo.id).update(status='A', ult_processamento=agora)
            else:
                Termo.objects.filter(id=termo.id).update(status='C', ult_processamento=agora)
        else:
            termos = Termo.objects.filter(status='A', dtinicio__lt=agora).order_by('ult_processamento')
            if termos.count() > 0:
                termo = Termo.objects.get(pk=termos[0].id)
                processo = Processamento.objects.create(termo=termo, dt=agora)
                Termo.objects.filter(id=termo.id).update(status='P')
                print('Search %s %d' % (termo.busca, processo.id))
                api = get_api()
                last = termo.last_tweet()
                # results = tweepy.Cursor(api.search, q=termo.busca, since_id=last, tweet_mode='extended', rpp=100).items()
                results = tweepy.Cursor(api.search, q=termo.busca, tweet_mode='extended').items()
                status_proc = ''
                for status in results:
                    save_result(status._json, processo.id)
                    agora = datetime.now(pytz.timezone(TIME_ZONE))
                    status_proc = Termo.objects.get(id=termo.id).status
                    if termo.dtfinal < agora:
                        print('Tempo finalizado %s' % agora)
                        break
                    if status_proc == 'I':
                        print('Processo interrompido')
                        break

                if termo.dtfinal < agora:
                    Termo.objects.filter(id=termo.id).update(status='C', ult_processamento=agora)
                else:
                    if status_proc != 'I':
                        Termo.objects.filter(id=termo.id).update(status='A', ult_processamento=agora)

                print('Processamento concluído')
            else:
                print('Nenhum termo para processar')
