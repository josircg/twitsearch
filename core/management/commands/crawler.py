import json
import requests
import time
import traceback

from datetime import timedelta, date, datetime
from django.core.management.base import BaseCommand
from django.db.transaction import set_autocommit, commit
from django.utils import timezone

from tweepy import BadRequest

from core import log_message, intdef
from core.opensearch import connect_opensearch, create_if_not_exists_index
from twitsearch.local import get_api_client

from django.conf import settings

from core.apps import save_result, find_first_tweet
from core.models import Termo, Rede, TweetInput, Processamento, PROC_PREMIUM, PROC_IMPORTACAO, PROC_FULL, PROC_CONTINUA

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

    def __init__(self, limite=2000, opensearch_client=None):
        self.since_id = None
        self.until_id = None
        self.tot_registros = 0
        self.limite = limite
        self.ultimo_tweet = 0
        self.menor_tweet = 0
        self.dt_inicial = None
        self.dt_final = None
        self.correcao = False
        self.client = opensearch_client

    def search_recent(self, processo, fake=False):
        agora = timezone.now()
        termo = processo.termo
        next_token = None

        print(f'\nProcesso {processo.id}')
        if termo.status == 'A':
            # Estratégia Contínua: irá continuar de onde parou utilizando o since_id
            self.since_id = termo.ult_tweet or 0
            if self.since_id == 0:
                self.since_id = None
                self.dt_inicial = termo.dtinicio
                if termo.dtfinal and termo.dtfinal < agora:
                    self.dt_final = termo.dtfinal
                print(f'Primeira execução {termo.id}: {self.dt_inicial} - {self.dt_final}')
            else:
                print(f'Execução regular {termo.id}: {self.since_id}')

        else:
            # Caso o Status seja 'I' então entra a Estratégia de Correção: irá buscar registros anteriores ao último capturado
            self.correcao = True
            self.since_id = None
            proc = Processamento.objects.filter(termo=termo, tipo=PROC_CONTINUA,
                                                status=Processamento.AGENDADO).order_by('-id').first()

            # Busca o último processamento anterior ao agendamento
            if proc:
                self.until_id = int(proc.twit_id)
                ult_proc = Processamento.objects.filter(termo=termo, tipo=termo.tipo_busca,
                                                        status=Processamento.CONCLUIDO,
                                                        twit_id__lt=self.until_id).exclude(twit_id='0').order_by('-id').first()
                if ult_proc and intdef(ult_proc.twit_id,0) != 0:
                    if termo.prim_tweet:
                        self.since_id = min(int(ult_proc.twit_id),termo.prim_tweet)
                    else:
                        self.since_id = int(ult_proc.twit_id)

            if not self.since_id:
                if not termo.prim_tweet:
                    termo.prim_tweet = find_first_tweet(termo)
                    termo.save()
                    commit()
                    # se não foi encontrado nenhum tweet então o termo não está trazendo nenhum registro!
                    if not termo.prim_tweet:
                        print('Nenhum registro encontrado para o termo')
                        next_token = 'Fim'
                self.since_id = termo.prim_tweet

            if not next_token:
                if not self.until_id:
                    primeiro = TweetInput.objects.filter(termo=termo, tweet_id__gt=self.since_id).order_by('tweet_id').first()
                    if primeiro:
                        self.until_id = int(primeiro.tweet_id)
                        print(f'Until: {self.until_id}')

                if self.since_id and self.since_id > self.until_id:
                    print('Não foi possível encontrar a faixa')
                    next_token = 'Fim'

                print(f'Rotina de Correção {termo.id}: {self.since_id} - {self.until_id}')

        # Caso não seja Full search e o último processamento tenha ultrapassado 7 dias, não considerar o since_id
        if termo.tipo_busca != PROC_FULL and self.dt_inicial:
            dt_limite_api = agora - timedelta(days=7) + timedelta(minutes=3)
            self.dt_inicial = max(self.dt_inicial, dt_limite_api)
            if termo.dtfinal and termo.dtfinal < agora:
                self.dt_final = termo.dtfinal
            self.since_id = None

        client = get_api_client()
        menor_data = agora.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        busca = termo.busca
        if termo.language:
            busca = f'{busca} lang:{termo.language}'

        if not termo.retweets:
            busca = f'{busca} -is:retweet'

        print(busca)

        if fake:
            return

        while self.tot_registros < self.limite and next_token != 'Fim':
            if termo.tipo_busca == PROC_FULL:
                tweets = client.search_all_tweets(
                             query=busca,
                             tweet_fields=API_FIELDS, media_fields=API_MEDIA_FIELDS, user_fields=API_USER_FIELDS, expansions=API_EXPANSIONS,
                             next_token=next_token,
                             since_id=self.since_id,
                             until_id=self.until_id,
                             start_time=self.dt_inicial,
                             end_time = self.dt_final,
                             max_results=100)
            else:
                tweets = client.search_recent_tweets(
                             query=busca,
                             tweet_fields=API_FIELDS, media_fields=API_MEDIA_FIELDS, user_fields=API_USER_FIELDS, expansions=API_EXPANSIONS,
                             next_token=next_token,
                             since_id=self.since_id,
                             start_time=self.dt_inicial,
                             end_time =self.dt_final,
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
                break

            # os tweets primários, retweets, replies e quotes são gravados em 'data'
            for indice, tweet in enumerate(tweets.source['data']):
                # os dados do autor devem ser reidratados no tweet original
                user_record = users.get(str(tweet['author_id']),None)
                if user_record:
                    tweet['user'] = user_record

                if len(tweets.data[indice].context_annotations) > 0:
                    tweet['context'] = tweets.data[indice].context_annotations

                save_result(tweet, processo, opensearch=self.client)
                if 'created_at' in tweet:
                    menor_data = min(menor_data, tweet['created_at'])
                current_id = intdef(tweet['id'],0)
                if current_id != 0:
                    self.ultimo_tweet = max(current_id, self.ultimo_tweet or current_id)
                    self.menor_tweet = min(current_id, self.menor_tweet or current_id)
                self.tot_registros += 1

            # os tweets pais (que geraram retweets ou quotes) são registrados nos includes
            if tweets.source['includes'].get('tweets'):
                for tweet in tweets.source['includes']['tweets']:
                    author_id = tweet.get('author_id', None)
                    # se o author do tweet original não estiver registrado, não gravar o pai
                    if author_id:
                        created_at = tweet.created_at.strftime("%Y-%m-%dT%H:%M:%S.000Z") if tweet.created_at else None
                        record = {
                            'id': tweet.id,
                            'author_id': tweet.author_id,
                            'user': users.get(str(author_id), None),
                            'created_at': created_at,
                            'text': tweet.text,
                            'public_metrics': tweet.public_metrics,
                            'lang': tweet.lang,
                            'geo': tweet.geo,
                        }
                        if tweet.referenced_tweets:
                            record['referenced_tweet'] = []
                            for ref in tweet.referenced_tweets:
                                record['referenced_tweet'].append(ref.data)

                        # o registro é gravado mas não será associado ao projeto
                        save_result(record, processo, grava_termo=False, overwrite=False, opensearch=self.client)
                        self.tot_registros += 1

            print(f'Total registros: {self.tot_registros} / {menor_data}')
            next_token = tweets.source.get('meta',{}).get('next_token','Fim')

        termo.ult_processamento = agora

        # marca o agendamento como concluído
        if self.correcao:
            if proc:
                proc.status = Processamento.CONCLUIDO
                proc.save()
        else:
            # se algum registro foi recebido, atualizar
            if self.tot_registros > 0 and self.ultimo_tweet:
                termo.ult_tweet = max(termo.ult_tweet or 0,self.ultimo_tweet)

        if self.tot_registros >= self.limite:
            termo.status = 'I'
            # Agenda o processamento de correção
            Processamento.objects.create(termo=termo, dt=agora, tipo=PROC_CONTINUA, status=Processamento.AGENDADO,
                                         twit_id=self.menor_tweet)
        else:
            # se for um processamento de correção que terminou, deve-se restaurar o último tweet carregado
            if self.correcao:
                proc = Processamento.objects.filter(termo=termo, tipo=PROC_CONTINUA).order_by('-twit_id').first()
                last = TweetInput.objects.filter(termo=termo).select_related('tweet').order_by('-tweet.twit_id').first()
                termo.ult_tweet = max(proc.twit_id, last.tweet.twit_id)

            # se a data atual for maior que o final programado
            if termo.dtfinal and menor_data > termo.dtfinal.strftime("%Y-%m-%dT%H:%M:%S.000Z"):
                print(f'Termo {termo.id} finalizado')
                termo.status = 'C'
            else:
                termo.status = 'A'
        termo.save()

        return

def processa_termo(termo, limite, fake_run):

    agora = timezone.now()
    mensagem = ''

    # se a data inicial já for superior a data final, concluir a carga
    if termo.tipo_busca == PROC_FULL:
        inicio_processamento = termo.dtinicio
    else:
        inicio_processamento = max(termo.dtinicio, agora - timedelta(days=7))

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

    if settings.OPENSEARCH_SERVERS:
        index_name = f"twitter-{agora.year}-{agora.month}"
        client = connect_opensearch('minerva-teste')
        if client and index_name:
            create_if_not_exists_index(client, index_name)
    else:
        client = None

    crawler = Crawler(limite, opensearch_client=client)
    try:
        crawler.search_recent(processo, fake_run)
        mensagem = f'{crawler.tot_registros} obtidos'
        commit()
        erro = False

    except BadRequest as e:
        if len(e.api_messages) > 0:
            mensagem = ''.join(e.api_messages)
        else:
            mensagem = f'Erro {e}\n'
        erro = True

    except Exception as e:
        mensagem = f'Erro {e}\n'
        mensagem += traceback.format_exc()
        erro = True

    finally:
        log_message(termo, mensagem)
        if erro:
            log_message(termo.projeto, f'Erro durante a captura do termo {termo.id}')
            print(f'Erro na montagem da busca. Termo:{termo.id} since_id:{crawler.since_id}')
            print(f'Data inicial:{crawler.dt_inicial} Data Final:{crawler.dt_final}')
            print(mensagem)

            if crawler.menor_tweet:
                Processamento.objects.create(termo=termo, dt=agora,
                                             tipo=PROC_CONTINUA, status=Processamento.AGENDADO,
                                             twit_id=crawler.menor_tweet)

            if crawler.ultimo_tweet != 0:
                Termo.objects.filter(id=termo.id).update(status='E', ult_tweet=crawler.ultimo_tweet)
            else:
                Termo.objects.filter(id=termo.id).update(status='E')

        processo.tot_registros = crawler.tot_registros
        processo.twit_id = crawler.ultimo_tweet
        processo.status = Processamento.CONCLUIDO
        processo.save()
        commit()


class Command(BaseCommand):
    label = 'Captura tweets de uma busca programada'

    def add_arguments(self, parser):
        parser.add_argument('--twit', type=str, help='Twitter ID')
        parser.add_argument('--proc', type=str, help='Processo')
        parser.add_argument('--termo', type=str, help='Termo ID')
        parser.add_argument('--limite', type=int, help='Limite de Tweets')
        parser.add_argument('--verbose', type=int, help='Aumento do Log')
        parser.add_argument('--fake', action='store_true', help='Indica quais os termos que seriam processados')

    def handle(self, *args, **options):

        limite = options['limite'] or 2000

        fake_run = options.get('fake')
        rede_twitter = Rede.objects.get(nome='Twitter/X')

        if 'twit' in options and options['twit']:
            processa_item_unico(options['twit'], options.get('termo'))
            return

        # Existem 3 estratégias de busca: Padrão, Contínua e Recuperação
        # Padrão: novo termo: começa do ínicio da carga do termo
        # Contínua: para cargas em andamento: começa do since_id
        # Recuperação: para caso de cargas com erro: calcula o último e usa até o último capturado
        if 'termo' in options and options['termo']:
            termo = Termo.objects.filter(id=options['termo']).first()
            if termo:
                processa_termo(termo, limite, fake_run)
            else:
                print('Termo não encontrado: %s' % options['termo'])
                return

        else:
            tot_termos = 0
            for termo in Termo.objects.filter(status__in=('A','I'), projeto__status='A',
                                              projeto__redes=rede_twitter).order_by('ult_processamento'):
                processa_termo(termo, limite, fake_run)
                time.sleep(2)
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