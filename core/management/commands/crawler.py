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
from django.db.transaction import set_autocommit, commit


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
        self.checkpoint = 10
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

        return self.dtfinal > convert_date(data['created_at'])

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
        termos = Termo.objects.filter(status='A', dtinicio__isnull=True)
        if termos.count() > 0:
            listener = SimpleListener()
            listener.processo = Processamento.objects.create(termo=termos[0], dt=agora)
            listener.dtfinal = termos[0].dtfinal
            Termo.objects.filter(id=termos[0].pk).update('P')
            print('Stream %d' % listener.processo.id)
            api = get_api()
            tweepy_stream = tweepy.Stream(auth=api.auth, listener=listener)
            tweepy_stream.filter(track=[termos[0].busca], is_async=True)
            while listener.checkpoint > 0 and listener.dtfinal < agora:
                time.sleep(360)
                agora = datetime.now(pytz.timezone(TIME_ZONE))
                listener.checkpoint -= 10
            Termo.objects.filter(id=termos[0].pk).update('C')
            print('Processamento concluído')
        else:
            termos = Termo.objects.filter(status='A', dtinicio__lt=agora)
            if termos.count() > 0:
                processo = Processamento.objects.create(termo=termos[0], dt=agora)
                Termo.objects.filter(id=termos[0].pk).update('P')
                print('Search %s %d' % (termos[0].busca, processo.id))
                api = get_api()
                results = tweepy.Cursor(api.search, q=termos[0].busca, tweet_mode='extended').items()
                for status in results:
                    save_result(status._json, processo.id)
                    agora = datetime.now(pytz.timezone(TIME_ZONE))
                    status = Termo.objects.get(id=termos[0].pk)[0].status
                    if termos[0].dtfinal < agora or status == 'I':
                        break
                Termo.objects.filter(id=termos[0].id).update('C')
                print('Processamento concluído')
            else:
                print('Nenhum termo para processar')
