import sys
import json
import pytz
import time
import traceback
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db.transaction import set_autocommit, commit, rollback

from core import log_message, intdef, convert_date
from twitsearch.local import get_api_client

import tweepy

from twitsearch.settings import TIME_ZONE
from core.apps import save_result
from core.models import Termo, Tweet, TweetInput, Processamento, PROC_PREMIUM, PROC_IMPORTACAO


def processa_item_unico(twitid, termo):
    agora = datetime.now(pytz.timezone(TIME_ZONE))
    termo = Termo.objects.get(id=termo)
    listener = SimpleListener()
    listener.processo = Processamento.objects.create(termo=termo, dt=agora)
    listener.dtfinal = termo.dtfinal
    api = get_api_client()
    tweets = api.search_recent_tweets(query=termo.busca,
                                      tweet_fields=['context_annotations', 'created_at'],
                                      max_results=10)
    tweepy_stream = tweepy.Stream(auth=api.auth, listener=listener)
    tweepy_stream.filter(track=[termo.busca], is_async=True)
    print('Twit %s importado' % twitid)


class SimpleListener():

    def __init__(self):
        # super(SimpleListener, self).__init__()
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

def busca_stream(termo, listener):
    agora = datetime.now(pytz.timezone(TIME_ZONE))
    api = get_api_client()
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

class Crawler:

    def __init__(self, limite=2000):
        self.since_id = None
        self.until_id = None
        self.tot_registros = 0
        self.limite = limite
        self.ultimo_tweet = 0

    def search_recent(self, processo):
        agora = timezone.now()
        dt_limite_api = agora - timedelta(days=7) + timedelta(minutes=2)
        termo = processo.termo
        if termo.status in ('A','P'):
            # Estratégia Contínua: irá continuar de onde parou
            self.since_id = termo.ult_tweet
            self.until_id = None
            if termo.ult_processamento and self.since_id is None:
                inicio_processamento = max(termo.ult_processamento, dt_limite_api)
            else:
                inicio_processamento = None
        else:
            # Estratégia de Correção: irá buscar registros mais antigos
            self.since_id = None
            first_tweet = TweetInput.objects.filter(termo=processo.termo, tweet__created_time__gt=dt_limite_api).first()
            if first_tweet:
                self.until_id = first_tweet.tweet.id
                inicio_processamento = None
            else:
                self.until_id = None
                inicio_processamento = None

        client = get_api_client()
        next_token = None
        while self.tot_registros < self.limite and next_token != 'Fim':
            tweets = client.search_recent_tweets(
                         query=termo.busca,
                         tweet_fields='text,created_at,public_metrics,author_id,conversation_id,lang,'
                                      'referenced_tweets,attachments,geo',
                         user_fields=['username', 'public_metrics', 'created_at', 'location'],
                         expansions=['author_id','referenced_tweets.id',
                                     'referenced_tweets.id.author_id'],
                         next_token=next_token,
                         since_id=self.since_id,
                         until_id=self.until_id,
                         start_time=inicio_processamento,
                         max_results=100)

            users = {}
            for user in tweets.source['includes']['users']:
                users[str(user['id'])] = {'username': user['username'], 'name': user['name'], 'verified': user['verified'],
                                          'followers_count': user['public_metrics']['followers_count'],
                                          'following_count': user['public_metrics']['following_count'],
                                          'tweet_count': user['public_metrics']['tweet_count']}

            # os tweets originais, retweets, replies e quotes são gravados em 'data'
            for tweet in tweets.source['data']:
                # os dados do autor devem ser reidratados no tweet original
                user_record = users.get(str(tweet['author_id']),None)
                if user_record:
                    tweet['user'] = user_record
                save_result(tweet, processo.id)
                self.ultimo_tweet = max(intdef(tweet['id'],0), self.ultimo_tweet)
                self.tot_registros += 1

            # os tweets pais (que geraram retweets ou quotes) são registrados nos includes
            for tweet in tweets.source['includes']['tweets']:
                author_id = tweet.get('author_id', None)
                if author_id:
                    # se o author do tweet original não estiver registrado, não gravar o pai
                    record = {
                        'id': tweet.id,
                        'author_id': tweet.author_id,
                        'user': users.get(str(author_id),None),
                        'created_at': tweet.created_at.strftime("%a %b %d %H:%M:%S %z %Y"),
                        'text': tweet.text,
                        'public_metrics': tweet.public_metrics,
                        'lang': tweet.lang,
                        'geo': tweet.geo,
                    }
                    if tweet.referenced_tweets:
                        record['referenced_tweet'] = []
                        for ref in tweet.referenced_tweets:
                            record['referenced_tweet'].append(ref.data)

                    save_result(record, processo.id, overwrite=False)
                    self.ultimo_tweet = max(intdef(record['id'],0), self.ultimo_tweet)
                    self.tot_registros += 1

            print(f'Total registros: {self.tot_registros}')
            next_token = tweets.source.get('meta',{}).get('next_token','Fim')

        # se o processo foi concluído antes do fim, então o número máximo de tweets foi alcançado
        if next_token != 'Fim':
            termo.status = 'C'
            termo.ult_tweet = self.ultimo_tweet
            termo.ult_processamento = agora
            termo.save()

        return

def processa_termo(termo, limite):

    agora = timezone.now()
    # se for um reset ou primeiro processamento
    if termo.status == 'A' or not termo.ult_tweet:
        if termo.dtinicio:
            inicio_processamento = termo.dtinicio
        else:
            inicio_processamento = agora - timedelta(days=7)
    else:
        inicio_processamento = max(termo.ult_processamento, agora - timedelta(days=7))

    if inicio_processamento > termo.dtfinal:
        termo.status = 'C'
        termo.save()
        mensagem = f'{termo.busca}: Busca Concluída. Fora do período possível ({inicio_processamento})'
        log_message(termo.projeto, mensagem)
        print(mensagem)
        return

    set_autocommit(False)
    processo = Processamento.objects.create(termo=termo, dt=agora,
                                            tipo=termo.tipo_busca, status=Processamento.PROCESSANDO)
    Termo.objects.filter(id=termo.id).update(status='P')
    commit()

    crawler = Crawler(limite)
    try:
        crawler.search_recent(processo)
        processo.twit_id = crawler.ultimo_tweet
        processo.tot_registros = crawler.tot_registros
        processo.status = Processamento.CONCLUIDO
        processo.save()
        Termo.objects.filter(id=termo.id).update(status='C',
                                                 ult_processamento=agora,
                                                 ult_tweet=crawler.ultimo_tweet)
        log_message(termo.projeto, f'{crawler.tot_registros} obtidos')
        commit()

    except Exception as e:
        mensagem = f'Erro {e}\n'
        mensagem += traceback.format_exc()
        print(mensagem)
        if crawler.ultimo_tweet != 0:
            Termo.objects.filter(id=termo.id).update(status='E',ult_tweet=crawler.ultimo_tweet)
        else:
            Termo.objects.filter(id=termo.id).update(status='E')
        processo.tot_registros = crawler.tot_registros
        processo.status = Processamento.CONCLUIDO
        processo.save()
        log_message(termo.projeto, mensagem)
        commit()


class Command(BaseCommand):
    label = 'Captura tweets de uma busca programada'

    def add_arguments(self, parser):
        parser.add_argument('--twit', type=str, help='Twitter ID')
        parser.add_argument('--proc', type=str, help='Processo')
        parser.add_argument('--termo', type=str, help='Termo ID')
        parser.add_argument('--limite', type=str, help='Limite de Tweets')

    def handle(self, *args, **options):
        if 'twit' in options and options['twit']:
            processa_item_unico(options['twit'], options['termo'])
            return

        if 'limite' in options:
            limite = intdef(options['limite'], 2000)
        else:
            limite = 2000

        # Existem 3 estratégias de busca: Padrão, Continua e Recuperação
        # Padrão: novo termo: começa do ínicio da carga do termo
        # Contínua: para cargas em andamento: começa do since_id
        # Recuperação: para caso de cargas com erro: calcula o último e usa o parâmetro until_id
        if 'termo' in options and options['termo']:
            termo = Termo.objects.filter(id=options['termo']).first()
            if not termo:
                print('Termo não encontrado: %s' % options['termo'])
                return
            processa_termo(termo, limite)
        else:
            tot_termos = 0
            for termo in Termo.objects.filter(status='A').order_by('ult_processamento'):
                processa_termo(termo, limite)
                tot_termos += 1

            if tot_termos == 0:
                print('Nenhum termo para processar %s' % timezone.now())
                return

        # Revive qualquer projeto de busca em processamento há mais de 1 horas
        uma_hora = timezone.now() - timedelta(hours=1)
        Termo.objects.filter(status='P',
                             tipo_busca__in=(PROC_IMPORTACAO, PROC_PREMIUM),
                             ult_processamento__lt=uma_hora).update(status='A')
        commit()