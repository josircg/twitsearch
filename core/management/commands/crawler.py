import json
import requests
import traceback
from django.utils import timezone

from datetime import timedelta, date
from django.core.management.base import BaseCommand
from django.db.transaction import set_autocommit, commit, rollback

from core import log_message, intdef, convert_date
from core.opensearch import connect_opensearch, create_if_not_exists_index
from twitsearch.local import get_api_client

from django.conf import settings

from core.apps import save_result
from core.models import Termo, Rede, TweetInput, Processamento, PROC_PREMIUM, PROC_IMPORTACAO, PROC_FULL

API_FIELDS = (
    "article,attachments,author_id,card_uri,community_id,context_annotations,conversation_id,created_at,public_metrics,"
    "entities,geo,id,in_reply_to_user_id,lang,media_metadata,note_tweet,possibly_sensitive,"
    "referenced_tweets,scopes,source,text,withheld")
API_EXPANSIONS = ['article.cover_media', 'article.media_entities', 'attachments.media_keys',
              'attachments.media_source_tweet', 'author_id', 'entities.mentions.username',
              'geo.place_id',
              'in_reply_to_user_id',
              'entities.note.mentions.username',
              'referenced_tweets.id',
              'referenced_tweets.id.attachments.media_keys',
              'referenced_tweets.id.author_id']
API_MEDIA_FIELDS = "alt_text,duration_ms,height,media_key,preview_image_url,public_metrics,type,url,variants,width"
API_PLACE_FIELDS = "contained_within,country,country_code,full_name,geo,id,name,place_type"
API_USER_FIELDS = "username,name,public_metrics,created_at,location"

def processa_item_unico(twit_id, termo_id):

    if termo_id:
        termo = Termo.objects.filter(id=termo_id).first()
    else:
        termo = None

    url = f"https://api.twitter.com/2/tweets/{twit_id}"
    headers = {
        "Authorization": f"Bearer {settings.BEARED_TOKEN}"
    }

    queryparams = {
        "tweet.fields": API_FIELDS,
        "media.fields": API_MEDIA_FIELDS,
        "place.fields": API_PLACE_FIELDS,
        "expansions": ','.join(API_EXPANSIONS),
        "user.fields": API_USER_FIELDS,
    }

    response = requests.get(url, headers=headers, params=queryparams)
    tweet = response.json()
    if 'errors' in tweet:
        print(f'Erro: {tweet}')
        return

    if termo:
        tweet['termo'] = termo.id
        tweet['projeto'] = termo.projeto.id

    filename = '%s/data/%s.json' % (settings.BASE_DIR, twit_id)
    with open(filename, 'w') as arquivo:
        json.dump(tweet, arquivo)


class Crawler:

    def __init__(self, limite=20000, index_name=None):
        self.since_id = None
        self.until_id = None
        self.tot_registros = 0
        self.limite = limite
        self.ultimo_tweet = 0
        self.dt_inicial = None
        self.client = connect_opensearch('minerva-teste')
        if self.client and index_name:
            create_if_not_exists_index(self.client, index_name)


    def search_recent(self, processo):
        agora = timezone.now()
        termo = processo.termo
        if termo.tipo_busca == PROC_FULL:
            dt_limite_api = date(1985,1,1)
        else:
            dt_limite_api = agora - timedelta(days=7) + timedelta(minutes=3)

        if termo.status in ('A','P'):
            # Estratégia Contínua: irá continuar de onde parou
            self.since_id = termo.ult_tweet
            if self.since_id == 0:
                self.since_id = None
            self.until_id = None
            if termo.ult_processamento and self.since_id is None:
                self.dt_inicial = max(termo.ult_processamento, dt_limite_api)
            else:
                # Caso o último processamento tenha ultrapassado 7 dias, não considerar o since_id
                if termo.ult_processamento and termo.ult_processamento < dt_limite_api:
                    self.since_id = None
                    self.dt_inicial = dt_limite_api
                else:
                    if termo.tipo_busca == PROC_FULL:
                        self.dt_inicial = termo.dtinicio
                    else:
                        self.dt_inicial = None
        else:
            # Caso o Status seja 'I' então entra a Estratégia de Correção: irá buscar registros mais antigos
            self.since_id = None
            first_tweet = TweetInput.objects.filter(termo=processo.termo, tweet__created_time__gt=dt_limite_api).first()
            if first_tweet:
                self.until_id = first_tweet.tweet.id
                self.dt_inicial = termo.dtinicio
            else:
                self.until_id = None
                if termo.tipo_busca == PROC_FULL:
                    self.dt_inicial = termo.dtinicio
                else:
                    self.dt_inicial = None

        client = get_api_client()
        next_token = None
        while self.tot_registros < self.limite and next_token != 'Fim':
            if termo.tipo_busca == PROC_FULL:
                tweets = client.search_all_tweets(
                             query=termo.busca,
                             tweet_fields=API_FIELDS, media_fields=API_MEDIA_FIELDS, user_fields=API_USER_FIELDS, expansions=API_EXPANSIONS,
                             next_token=next_token,
                             since_id=self.since_id,
                             until_id=self.until_id,
                             start_time=self.dt_inicial,
                             max_results=100)
            else:
                tweets = client.search_recent_tweets(
                             query=termo.busca,
                             tweet_fields=API_FIELDS, media_fields=API_MEDIA_FIELDS, user_fields=API_USER_FIELDS, expansions=API_EXPANSIONS,
                             next_token=next_token,
                             since_id=self.since_id,
                             until_id=self.until_id,
                             start_time=self.dt_inicial,
                             max_results=100)

            if tweets.source.get('meta'):
                if tweets.source['meta'].get('result_count',0) == 0:
                    break

            users = {}
            if tweets.source.get('includes'):
                for user in tweets.source['includes']['users']:
                    users[str(user['id'])] = {'username': user['username'], 'name': user['name'], 'verified': user['verified'],
                                              'followers_count': user['public_metrics']['followers_count'],
                                              'following_count': user['public_metrics']['following_count'],
                                              'tweet_count': user['public_metrics']['tweet_count']}
            else:
                print('No includes found', tweets.source)
                print(self.since_id, self.until_id, self.dt_inicial)
                break

            # os tweets originais, retweets, replies e quotes são gravados em 'data'
            for tweet in tweets.source['data']:
                # os dados do autor devem ser reidratados no tweet original
                user_record = users.get(str(tweet['author_id']),None)
                if user_record:
                    tweet['user'] = user_record
                save_result(tweet, processo, opensearch=self.client)
                self.ultimo_tweet = max(intdef(tweet['id'],0), self.ultimo_tweet)
                self.tot_registros += 1

            # os tweets pais (que geraram retweets ou quotes) são registrados nos includes
            if tweets.source['includes'].get('tweets'):
                for tweet in tweets.source['includes']['tweets']:
                    author_id = tweet.get('author_id', None)
                    if author_id:
                        # se o author do tweet original não estiver registrado, não gravar o pai
                        record = {
                            'id': tweet.id,
                            'author_id': tweet.author_id,
                            'user': users.get(str(author_id), None),
                            'created_at': tweet.created_at.strftime("%Y-%m-%dT%H:%M:%S.000Z") if tweet.created_at else None,
                            'text': tweet.text,
                            'public_metrics': tweet.public_metrics,
                            'lang': tweet.lang,
                            'geo': tweet.geo,
                        }
                        if tweet.referenced_tweets:
                            record['referenced_tweet'] = []
                            for ref in tweet.referenced_tweets:
                                record['referenced_tweet'].append(ref.data)

                        save_result(record, processo, overwrite=False, opensearch=self.client)
                        self.ultimo_tweet = max(intdef(record['id'],0), self.ultimo_tweet)
                        self.tot_registros += 1

            print(f'Total registros: {self.tot_registros}')
            next_token = tweets.source.get('meta',{}).get('next_token','Fim')

        # se algum registro foi recebido, atualizar os status do termo
        if self.tot_registros > 0:
            if self.ultimo_tweet:
                termo.ult_tweet = self.ultimo_tweet
            termo.ult_processamento = agora

        if self.tot_registros >= self.limite:
            termo.status = 'I'
        elif termo.dtfinal and agora > termo.dtfinal:
        # se a data atual for maior que o final programado
            print(f'Termo {termo.id} finalizado')
            termo.status = 'C'
        else:
            termo.status = 'A'
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

    if termo.dtfinal and inicio_processamento > termo.dtfinal:
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
    
    index_name = f"twitter-{agora.year}-{agora.month}"
    crawler = Crawler(limite, index_name=index_name)
    try:
        crawler.search_recent(processo)
        processo.twit_id = crawler.ultimo_tweet
        processo.tot_registros = crawler.tot_registros
        processo.status = Processamento.CONCLUIDO
        processo.save()
        log_message(termo.projeto, f'{crawler.tot_registros} obtidos')
        commit()

    except Exception as e:
        mensagem = f'Erro {e}\n'
        mensagem += traceback.format_exc()
        if crawler.ultimo_tweet != 0:
            Termo.objects.filter(id=termo.id).update(status='E',ult_tweet=crawler.ultimo_tweet)
        else:
            Termo.objects.filter(id=termo.id).update(status='E')
        processo.tot_registros = crawler.tot_registros
        processo.status = Processamento.CONCLUIDO
        processo.save()
        log_message(termo, mensagem)
        log_message(termo.projeto, 'Erro durante a captura do termo {termo.id}')
        print(f'Erro na montagem da busca. Termo:{termo.id}')
        print(f'since_id:{crawler.since_id}')
        print(f'until_id:{crawler.until_id}')
        print(f'Data inicial:{crawler.dt_inicial}')
        print(mensagem)
        commit()


class Command(BaseCommand):
    label = 'Captura tweets de uma busca programada'

    def add_arguments(self, parser):
        parser.add_argument('--twit', type=str, help='Twitter ID')
        parser.add_argument('--proc', type=str, help='Processo')
        parser.add_argument('--termo', type=str, help='Termo ID')
        parser.add_argument('--limite', type=int, help='Limite de Tweets')
        parser.add_argument('--fake', action='store_true', help='Indica quais os termos que seriam processados')

    def handle(self, *args, **options):

        limite = options['limite'] or 20000

        fake_run = options.get('fake')
        rede_twitter = Rede.objects.get(nome='Twitter/X')

        if 'twit' in options and options['twit']:
            processa_item_unico(options['twit'], options.get('termo'))
            return

        # Existem 3 estratégias de busca: Padrão, Contínua e Recuperação
        # Padrão: novo termo: começa do ínicio da carga do termo
        # Contínua: para cargas em andamento: começa do since_id
        # Recuperação: para caso de cargas com erro: calcula o último e usa o parâmetro until_id
        if 'termo' in options and options['termo']:
            termo = Termo.objects.filter(id=options['termo']).first()
            if termo:
                processa_termo(termo, limite)
            else:
                print('Termo não encontrado: %s' % options['termo'])
                return

        else:
            tot_termos = 0
            for termo in Termo.objects.filter(status='A', projeto__status='A',
                                              projeto__redes=rede_twitter).order_by('ult_processamento'):
                if fake_run:
                    print(termo.projeto, termo.busca, termo.ult_tweet)
                else:
                    processa_termo(termo, limite)
                tot_termos += 1

            if tot_termos == 0:
                print('Nenhum termo para processar %s' % timezone.now())
                return

        # Revive qualquer projeto de busca em processamento há mais de 1 horas
        uma_hora = timezone.now() - timedelta(hours=1)
        Termo.objects.filter(status='P',
                             tipo_busca__in=(PROC_IMPORTACAO, PROC_PREMIUM, PROC_FULL),
                             ult_processamento__lt=uma_hora).update(status='A')
        commit()