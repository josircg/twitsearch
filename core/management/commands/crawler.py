# -*- coding: utf-8 -*-
import json
import pytz
import time
import traceback
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db.transaction import set_autocommit, commit, rollback

from core import log_message, intdef, convert_date
from twitsearch.local import get_api

import tweepy
from searchtweets import ResultStream, gen_request_parameters, load_credentials

from twitsearch.settings import TIME_ZONE
from core.models import Termo, Tweet, Processamento, PROC_PREMIUM, PROC_IMPORTACAO


def save_result(data, processo, v2=False):
    data['process'] = processo
    if v2:
        filename = 'data/%s_.json' % data['id']
    else:
        filename = 'data/%s.json' % data['id']
    arquivo = open(filename, 'w')
    json.dump(data, arquivo)
    arquivo.close()
    # print('%s saved' % filename)


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


class SimpleListener(tweepy.StreamListener):

    def __init__(self):
        super(SimpleListener, self).__init__()
        self.checkpoint = 120 # 2 minutos para começar a receber algum tweet
        self.processo = None
        self.dtfinal = None
        self.menor_data = None
        self.count = 0
        self.status = 'A'

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


# A busca por período pega tudo para o futuro, independente da data final
# O controle do fim do processo é feito quando a menor data encontrada for maior que a data final
class RegularListener:

    def __init__(self):
        self.processo = None
        self.menor_data = None
        self.maior_data = None
        self.count = 0
        self.ultimo_tweet = 0    # Último tweet capturado
        self.status = 'A'
        self.proc_limit = 100000  # Quantos registos traz por processamento

    def run(self):
        termo = self.processo.termo
        termo_busca = termo.busca
        if termo.ult_tweet:
            since_id = termo.ult_tweet
            termo_busca += ' since_id:%d' % termo.ult_tweet
        else:
            since_id = None

        print('Search: "%s" %d %d since:%s' % (termo.busca, self.processo.id, termo.id, since_id))
        self.count = 0
        api = get_api()
        results = tweepy.Cursor(api.search, q=termo.busca, tweet_mode='extended', since_id=since_id).items()
        # results = tweepy.Cursor(api.search, q=termo.busca+extra_filter, since_id=ultimo,
        #                         tweet_mode='extended', rpp=100, page=10).items()
        for tweet in results:
            created = tweet.created_at.replace(tzinfo=timezone.utc)
            if tweet.id > self.ultimo_tweet:
                self.ultimo_tweet = tweet.id
                if not self.maior_data:
                    self.maior_data = created
                else:
                    self.maior_data = max(self.maior_data, created)

            save_result(tweet._json, self.processo.id)
            self.count += 1
            if not self.menor_data:
                self.menor_data = created
            else:
                self.menor_data = min(self.menor_data, created)

        return


class PremiumListener:

    def __init__(self):
        self.processo = None
        self.menor_data = None
        self.count = 0
        self.ultimo_tweet = ''     # Último tweet capturado
        self.status = 'A'
        self.proc_limit = 1000000   # Quantos registos traz por processamento

    def run(self):
        auth = load_credentials(filename="twitsearch/credentials.yaml",
                                yaml_key="oldimar",
                                env_overwrite=False)
        termo = self.processo.termo
        if not self.menor_data:
            if termo.ult_processamento:
                # A busca dos tweets é feita do mais recente para o mais antigo
                # Desta forma, em caso de reprocessamento, a data final será deslocada para o tweet mais recente
                self.ultimo_tweet = str(termo.ult_tweet)
                tweet = Tweet.objects.filter(twit_id=self.ultimo_tweet, created_time__gte=termo.dtinicio).first()
                if not tweet:
                    tweet = Tweet.objects.filter(termo=termo, created_time__gte=termo.dtinicio).\
                        order_by('-twit_id').first()

                if tweet:
                    self.menor_data = tweet.created_time
                else:
                    self.menor_data = termo.dtfinal

            else:
                self.menor_data = termo.dtfinal

        start_time = termo.dtinicio.strftime('%Y-%m-%d %H:%M')
        limite_premium = datetime.now(pytz.timezone(TIME_ZONE)) - timedelta(days=1)
        if self.menor_data > limite_premium:
            end_time = limite_premium.strftime('%Y-%m-%d %H:%M')
            print(f'Limit - Start: {start_time}  End: {end_time}')
        else:
            end_time = self.menor_data.strftime('%Y-%m-%d %H:%M')
            print(f'Reload - Start: {start_time}  End: {end_time}')
        self.count = 0
        tot_calls = 0
        query = gen_request_parameters(termo.busca, None,
                                       tweet_fields='id,text,public_metrics,author_id,conversation_id,created_at,'
                                                    'lang,in_reply_to_user_id,possibly_sensitive,'
                                                    'referenced_tweets',
                                       user_fields='id,name,username,created_at,public_metrics,verified',
                                       expansions='author_id,referenced_tweets.id,referenced_tweets.id.author_id',
                                       results_per_call=500,
                                       start_time=start_time, end_time=end_time)
        tweets = ResultStream(request_parameters=query, max_tweets=self.proc_limit, **auth)
        for dataset in tweets.stream():

            # Monta a matriz de usuários
            users = {}
            for user in dataset['includes']['users']:
                user['screen_name'] = user['username']
                del user['username']
                user['followers_count'] = user['public_metrics']['followers_count']
                user['favourites_count'] = user['public_metrics']['following_count']

            # Converte o tweet para o formato da API v1
            for tweet in dataset['data']:
                # save_result(tweet, self.processo.id, True)
                self.menor_data = min(self.menor_data, convert_date(tweet['created_at']))
                if self.ultimo_tweet == '':
                    self.ultimo_tweet = tweet['id']
                else:
                    self.ultimo_tweet = min(self.ultimo_tweet, tweet['id'])

                tweet['retweet_count'] = tweet['public_metrics']['retweet_count']
                tweet['reply_count'] = tweet['public_metrics']['reply_count']
                tweet['favorite_count'] = tweet['public_metrics']['like_count']
                del tweet['public_metrics']
                if tweet['author_id'] in users:
                    tweet['user'] = users[tweet['author_id']]
                else:
                    tweet['user'] = {'id': tweet['author_id']}

                for parent in tweet.get('referenced_tweets', []):
                    if 'public_metrics' in parent:
                        parent['retweet_count'] = parent['public_metrics']['retweet_count']
                        parent['reply_count'] = parent['public_metrics']['reply_count']
                        parent['favorite_count'] = parent['public_metrics']['like_count']
                        del parent['public_metrics']

                    if 'author' in parent:
                        parent['user'] = parent['author']
                        del parent['author']
                    else:
                        if 'author_id' in parent:
                            if parent['author_id'] in users:
                                parent['user'] = users[ parent[ 'author_id' ] ]
                            else:
                                parent['user'] = {'id': parent[ 'author_id' ]}
                        else:
                            if 'in_reply_to_user' in tweet:
                                parent['user'] = tweet['in_reply_to_user']

                    if parent['type'] in ('replied_to', 'quoted'):
                        tweet['quoted_status'] = parent
                    else:
                        tweet['retweeted_status'] = parent

                save_result(tweet, self.processo.id, False)
                self.count += 1

            # Verifica se o usuário interrompeu o processamento
            self.status = Termo.objects.get(id=termo.id).status
            if self.status == 'I':
                break

            sleep_count = min(2*tot_calls, 120)
            print(f'{self.count} tweets importados (soneca:{sleep_count})')
            time.sleep(sleep_count)
            tot_calls += 1

        if self.count < self.proc_limit and self.status != 'I':
            self.status = 'C'

        return


def busca_stream(termo, listener):
    agora = datetime.now(pytz.timezone(TIME_ZONE))
    api = get_api()
    termo_busca = termo.busca
    print('Stream %d %s' % (listener.processo.id, termo_busca))
    tweepy_stream = tweepy.Stream(auth=api.auth, listener=listener)
    tweepy_stream.filter(track=[termo_busca], is_async=True)
    listener.status = 'P'
    while listener.checkpoint > 0 and listener.dtfinal > agora and listener.status == 'P':
        print('Sleeping')
        time.sleep(listener.checkpoint + listener.count)
        agora = datetime.now(pytz.timezone(TIME_ZONE))
        # Verifica se o processo não foi interrompido pelo usuário
        listener.status = Termo.objects.get(id=termo.id).status
        listener.checkpoint -= 100
        print('Checkpoint %d' % listener.checkpoint)

    # se saiu do loop pois ficou muito tempo sem encontrar tweets, mantem a busca ativa
    tweepy_stream.disconnect()
    return


class Command(BaseCommand):
    label = 'Captura tweets de uma busca programada'

    def add_arguments(self, parser):
        parser.add_argument('--twit', type=str, help='Twitter ID')
        parser.add_argument('--proc', type=str, help='Processo')
        parser.add_argument('--termo', type=str, help='Termo ID')

    def handle(self, *args, **options):
        agora = timezone.now()
        registros_lidos = 0
        if 'twit' in options and options['twit']:
            processa_item_unico(options['twit'], options['termo'])
            return

        if 'termo' in options and options['termo']:
            termo = Termo.objects.filter(id=options['termo']).first()
            reset_search = True
        else:
            termo = Termo.objects.filter(status='A').order_by('ult_processamento').first()
            reset_search = False

        if not termo:
            print('Nenhum termo para processar %s' % timezone.now())
            return

        # se for um reset ou primeiro processamento
        if reset_search or not termo.ult_tweet:
            ultimo_tweet = None
            if termo.tipo_busca == PROC_PREMIUM:
                inicio_processamento = termo.dtinicio
            else:
                inicio_processamento = max(termo.dtinicio, agora - timedelta(days=14))
        else:
            ultimo_tweet = termo.ult_tweet
            if termo.tipo_busca == PROC_PREMIUM:
                inicio_processamento = termo.dtinicio
            else:
                if termo.ult_processamento:
                    inicio_processamento = max(termo.ult_processamento, agora - timedelta(days=14))
                else:
                    inicio_processamento = max(termo.dtinicio, agora - timedelta(days=14))

            if inicio_processamento > termo.dtfinal:
                termo.status = 'C'
                termo.save()
                mensagem = f'Busca fora do período possível {termo.busca} {termo.dtfinal}'
                log_message(termo.projeto, mensagem)
                print(mensagem)
                return

        set_autocommit(False)
        processo = Processamento.objects.create(termo=termo, dt=agora,
                                                tipo=termo.tipo_busca, status=Processamento.PROCESSANDO)
        Termo.objects.filter(id=termo.id).update(status='P')
        commit()

        try:
            if termo.tipo_busca == PROC_PREMIUM:
                listener = PremiumListener()
                listener.processo = processo
                if reset_search:
                    listener.menor_data = processo.termo.dtfinal
                listener.run()
                proxima_data = agora
                registros_lidos = listener.count
                status_proc = listener.status
            else:
                # Se foi anterior que hoje, busca-se primeiro termos antigos
                if inicio_processamento.date() < agora.date():
                    status_proc = 'A'
                    listener = RegularListener()
                    listener.processo = processo
                    listener.run()
                    registros_lidos = listener.count

                else:
                    # Se o último processamento foi hoje, a busca é feita via stream para obter novos tweets
                    listener = SimpleListener()
                    listener.processo = processo
                    listener.dtfinal = termo.dtfinal
                    busca_stream(termo, listener)
                    registros_lidos = listener.count

                proxima_data = agora
                # recalcula o status da busca em função da data final do projeto
                if listener.menor_data and termo.dtfinal < listener.menor_data:
                    status_proc = 'C'
                else:
                    # se não nenhum registro foi baixado ou se o processo foi interrompido pelo usuário
                    # então agenda-se o próximo processamento para 1 hora depois
                    status_proc = listener.status
                    if status_proc == 'A':
                        if registros_lidos == 0:
                            proxima_data = agora + timedelta(hours=1)
                        else:
                            proxima_data = agora + timedelta(hours=2)

            # Sinaliza o fim do processamento
            print('Status atualizado (%d): %s %s' % (termo.id, status_proc, listener.ultimo_tweet))
            Termo.objects.filter(id=termo.id).update(status=status_proc,
                                                     ult_processamento=proxima_data,
                                                     ult_tweet=listener.ultimo_tweet)
            processo.twit_id = listener.ultimo_tweet
            processo.status = Processamento.CONCLUIDO
            processo.save()
            commit()

            # Revive qualquer projeto de busca simples em processamento há mais de 1 horas
            uma_hora = agora - timedelta(hours=1)
            Termo.objects.filter(status='P', tipo_busca=PROC_IMPORTACAO, ult_processamento__lt=uma_hora).\
                update(status='A')
            commit()

        except Exception as e:
            if listener:
                ultimo_tweet = intdef(listener.ultimo_tweet, 0)
            else:
                ultimo_tweet = termo.ult_tweet
            Termo.objects.filter(id=termo.id).update(status='E', ult_processamento=agora,
                                                     ult_tweet=ultimo_tweet)
            processo.status = Processamento.CONCLUIDO
            processo.save()
            commit()
            mensagem = 'Erro no processamento: %s' % e
            log_message(termo.projeto, mensagem)
            print(mensagem)
            traceback.print_exc()
            return

        print('Processamento concluído: %d registros lidos' % registros_lidos)
