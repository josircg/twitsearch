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
        self.checkpoint = 20
        self.processo = None
        self.dtfinal = None
        self.menor_data = None
        self.count = 0

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
        self.count += 1
        created = convert_date(data['created_at']).replace(tzinfo=timezone.utc)
        if not self.menor_data or created < self.menor_data:
            self.menor_data = created

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

        if termo.ult_processamento:
            ult_processamento = max(termo.ult_processamento, agora - timedelta(days=7))
        else:
            ult_processamento = max(termo.dtinicio, agora - timedelta(days=7))

        processo = Processamento.objects.create(termo=termo, dt=agora)
        Termo.objects.filter(id=termo.id).update(status='P')

        # Se o último processamento foi hoje, a busca é feita via stream para obter novos tweets
        # Se foi anterior que hoje ou nula, busca-se primeiro termos antigos
        if ult_processamento.date() < agora.date():
            api = get_api()
            termo_busca = termo.busca
            if ultimo:
                since_id = ultimo
                termo_busca += ' since_id:%d' % ultimo
                maior_data = termo.ult_processamento
                menor_data = termo.ult_processamento
            else:
                since_id = None
                ultimo = 0
                maior_data = ult_processamento
                menor_data = ult_processamento
            # results = tweepy.Cursor(api.search, q=termo.busca+extra_filter, since_id=ultimo,
            #                         tweet_mode='extended', rpp=100, page=10).items()

            print('Search: "%s" %d %d since:%s' % (termo.busca, processo.id, termo.id, since_id))
            results = tweepy.Cursor(api.search, q=termo.busca, tweet_mode='extended', since_id=since_id).items()
            try:
                registros_lidos = 0
                for status in results:
                    if status.id > ultimo:
                        ultimo = status.id
                        created = status.created_at.replace(tzinfo=timezone.utc)
                        maior_data = max(maior_data, created)

                    save_result(status._json, processo.id)
                    registros_lidos += 1
                    menor_data = min(menor_data, created)

            except Exception as e:
                print('API Timeout: %s' % e.__str__())
        else:
            listener = SimpleListener()
            listener.processo = Processamento.objects.create(termo=termo, dt=agora)
            listener.dtfinal = termo.dtfinal
            api = get_api()
            termo_busca = termo.busca
            print('Stream %d %s' % (listener.processo.id, termo_busca))
            tweepy_stream = tweepy.Stream(auth=api.auth, listener=listener)
            tweepy_stream.filter(track=[termo_busca], is_async=True)
            status_proc = 'P'
            while listener.checkpoint > 0 and listener.dtfinal > agora and status_proc == 'P':
                print('Sleeping')
                time.sleep(listener.checkpoint+listener.count)
                agora = datetime.now(pytz.timezone(TIME_ZONE))
                status_proc = Termo.objects.get(id=termo.id).status
                listener.checkpoint += listener.count - 10
                print('Checkpoint %d' % listener.checkpoint)

            # se saiu do loop pois ficou muito tempo sem encontrar tweets, mantem a busca ativa
            tweepy_stream.disconnect()
            menor_data = listener.menor_data
            registros_lidos = listener.count

        if menor_data and termo.dtfinal < menor_data:
            status_proc = 'C'
        else:
            status_proc = 'A' if status_proc != 'I' else 'I'
            # se não nenhum registro foi baixado, então agenda-se o próximo processamento para 1 hora depois
            if registros_lidos == 0:
                menor_data = agora + timedelta(hours=1)

        # Sinaliza o fim do processamento
        Termo.objects.filter(id=termo.id).update(status=status_proc,
                                                 ult_processamento=menor_data,
                                                 ult_tweet=ultimo)
        processo.twit_id = ultimo
        processo.save()

        # Revive qualquer projeto em processamento há mais de 1 horas
        uma_hora = agora - timedelta(hours=1)
        Termo.objects.filter(status='P', ult_processamento__lt=uma_hora).update(status='A')

        print('Processamento concluído: %d registros lidos' % registros_lidos)
