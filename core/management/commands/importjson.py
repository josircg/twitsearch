import json
import os
import traceback

from os import rename, makedirs
from os.path import isfile, join, exists

from django.conf import settings
from django.utils import timezone
from django.db.transaction import set_autocommit, commit, rollback
from django.core.management.base import BaseCommand

from core import convert_date, intdef, log_message
from core.models import *

# tentativa de remover tweets que não faziam referência à busca.
# Não funcionou pois o Twitter realiza a busca nos títulos das URLs adicionadas
def find_termo(termo, texto):
    for palavra in termo.upper().split(' OR '):
        cleaned = clean_pontuation(palavra)
        if cleaned.strip() in texto.upper():
            return True
    return False

class Processo:

    def __init__(self, processo_db):
        self.processamento = processo_db
        self.counter_users = 0
        self.counter_tweets = 0
        self.counter_retweets = 0
        self.termos = []
        if self.processamento.termo:
            self.termos.append(processo_db.termo.id)

    def create_reference(self, parent_tweet, tweet_type, new_id, user, dt):
        retweet, created = Retweet.objects.get_or_create(retweet_id=new_id,
                                                         parent_id=parent_tweet['id'],
                                                         defaults={'user': user, 'created_time': dt,
                                                                   'type': tweet_type})
        if 'user' in parent_tweet or 'author_id' in parent_tweet:
            parent, related_user = self.load_twitter(parent_tweet)
            if not retweet.tweet and parent:
                retweet.tweet = parent
            if not retweet.related_user and related_user:
                retweet.related_user = related_user
            retweet.save()

        if created:
            self.counter_retweets += 1

    # https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/intro-to-tweet-json
    def load_twitter(self, src):

        if 'author_id' in src:
            user_id = src['author_id']
        elif 'user' in src:
            user_id = src['user'].get('id',None)
        else:
            user_id = None

        # se não houver o mínimo de elementos para registrar um novo tweet, a rotina tenta encontrar o tweet
        new_user = False
        tweet = None
        if not user_id and 'id' in src:
            tweet = Tweet.objects.filter(twit_id=src['id']).first()
            if tweet:
                user = tweet.user
            else:
                user = None
        else:
            try:
                user = TweetUser.objects.get(twit_id=user_id)
            except TweetUser.DoesNotExist:
                new_user = True
                user = TweetUser(twit_id=user_id, verified=False)
                self.counter_users += 1

        # se contiver info sobre o usuário, verificar se é necessário preencher os campos
        if 'user' in src:
            username =  src['user'].get('username',src['user'].get('screen_name',None))
        else:
            username = None

        if user and not user.username and username:
            user.username = username
            user.name = src['user'].get('name', None)
            user.verified=src['user'].get('verified',None)
            if user.verified is None:
                user.verified = False
            if 'created_at' in src['user']:
                user.created_at=convert_date(src['user']['created_at']).date()
            user.save()
        else:
            if new_user:
                user.save()

        if 'created_at' in src:
            dt = convert_date(src['created_at'])
        else:
            # se não tem o created_at então é um retweet/quoted sem info
            return tweet, user

        # Indica que é um JSON da API v1
        if 'user' in src and 'followers_count' in src['user']:
            try:
                FollowersHistory.objects.get(user=user, dt=dt)
            except FollowersHistory.DoesNotExist:
                # na API v1, a coluna era friends_count. Na API v2, a coluna passou ser following_count
                following_count = src['user'].get('friends_count',0) + src['user'].get('following_count',0)
                favourite_count = src['user'].get('favourites_count',0)
                follow = FollowersHistory(user=user, dt=dt,
                                          followers=src['user']['followers_count'],
                                          following=following_count,
                                          favourites=favourite_count)
                follow.save()

            follow = FollowersHistory.objects.filter(user=user).latest('dt')
            if user.followers != follow.followers:
                user.followers = follow.followers
                user.save()

        if 'process' in src and src['process'] != self.processamento:
            try:
                processo_atual = Processamento.objects.get(id=src['process'])
            except Processamento.DoesNotExist:
                processo_atual = self.processamento

            if processo_atual.termo and processo_atual.termo.id not in self.termos:
                self.termos.append( processo_atual.termo.id )
        else:
            processo_atual = self.processamento

        # Quoted é o retweet com comentário
        # C-Comentário no tweet pai, Q-Quoted, R-Retweet
        if 'quoted_status' in src and 'id' in src['quoted_status']:
            if 'type' in src['quoted_status']:
                tweet_type = 'Q' if src['quoted_status']['type'] == 'quoted' else 'C'
            else:
                tweet_type = 'Q'
            self.create_reference(src['quoted_status'], tweet_type, src['id'], user, dt)
            retweet = False

        elif 'retweeted_status' in src and 'id' in src['retweeted_status']:
            self.create_reference(src['retweeted_status'], 'R', src['id'], user, dt)
            retweet = True

        elif 'referenced_tweets' in src:
            retweet = True
            for parent_tweet in src['referenced_tweets']:
                ref_type = parent_tweet['type']
                if ref_type == 'retweeted':
                    tweet_type = 'R'
                elif ref_type == 'replied_to':
                    tweet_type = 'C'
                    retweet = False
                else:
                    tweet_type = 'Q'
                    retweet = False
                self.create_reference(parent_tweet, tweet_type, src['id'], user, dt)

        else:
            retweet = False

        # Retweet não tem comentário,
        # logo o tweet corrente só é gravado se tiver um novo texto associado
        if not retweet:

            if 'full_text' in src:
                texto = src['full_text']
            else:
                texto = src['text']

            try:
                tweet = Tweet.objects.get(twit_id=src['id'])
                tweet.termo = tweet.termo or processo_atual.termo
            except Tweet.DoesNotExist:
                tweet = Tweet(
                            twit_id=src['id'], user=user, text=texto,
                            created_time=dt,
                            retweets=0,
                            favorites=0,
                            imprints=0,
                            termo=processo_atual.termo)
                self.counter_tweets += 1

            tweet.language = src.get('lang', tweet.language)
            tweet.location = src.get('location', tweet.location)
            tweet.geo = src.get('geo', tweet.geo)

            if 'public_metrics' in src:
                retweets_count = src['public_metrics'].get('retweet_count',0)
                favorites_count = src['public_metrics'].get('like_count',0)
                imprints = src['public_metrics'].get('impression_count',0)
            else:
                retweets_count = src.get('retweet_count',0)
                favorites_count = src.get('favorite_count',0)
                imprints = src.get('impression_count',0)

            tweet.retweets = max(retweets_count, intdef(tweet.retweets,0))
            tweet.favorites = max(favorites_count, intdef(tweet.favorites,0))
            tweet.imprints = max(imprints, intdef(tweet.imprints,0))
            tweet.save()

            # se a data do tweet for maior que a data programada para o termo, não grava o termo
            termo = processo_atual.termo
            if termo and tweet.created_time > termo.dtfinal:
                termo = None

            TweetInput.objects.get_or_create(tweet=tweet, termo=termo,
                                             defaults={'processamento': processo_atual})

        return tweet, user


class Command(BaseCommand):
    label = 'Importa Tweets'

    def add_arguments(self, parser):
        parser.add_argument('twit', type=str, help='Twitter File',)
        parser.add_argument('-p', '--processo', type=str, help='Processo Default', nargs='?')
        parser.add_argument('-j', '--projeto', type=str, help='Projeto Default', nargs='?')
        parser.add_argument('-f', '--force', help='Accept multiple imports running', action='store_true')
        parser.add_argument('-o', '--optimize', help='Do not import duplicate files', action='store_true')

    def handle(self, *args, **options):

        force = options.get('force')
        optimize = options.get('optimize')
        processo_ativo = None
        termo = None
        if options['projeto']:
            termo = Termo.objects.filter(projeto_id=options['projeto']).first()
            if not termo:
                self.stdout.write(self.style.ERROR('Nenhum termo ativo para o projeto %s' % options['projeto']))
                return
            processo_ativo = Processamento.objects.filter(termo=termo, tipo=PROC_IMPORTACAO).first()
        elif options['processo']:
            try:
                processo_ativo = Processamento.objects.get(id=options['processo'])
            except Processamento.DoesNotExist:
                # Se o processo determinado não foi encontrado, deve-se interromper a rotina
                self.stdout.write(self.style.WARNING('Processo %s não encontrado' % options['processo']))
                return

        # se o processamento não foi indicado como entrada ou se nenhum processo existe para o termo indicado
        if not processo_ativo:
            if force:
                Processamento.objects.filter(status=Processamento.PROCESSANDO, tipo=PROC_JSON_IMPORT).\
                    update(status=Processamento.CONCLUIDO)
                print('Force Update')
            else:
                proc = Processamento.objects.filter(status=Processamento.PROCESSANDO, tipo=PROC_JSON_IMPORT)
                if proc:
                    print('Importação pendente %d' % proc[0].id)
                    return
            agora = timezone.now()
            processo_ativo = Processamento.objects.create(status=Processamento.PROCESSANDO,
                                                          tipo=PROC_JSON_IMPORT, dt=agora, termo=termo,
                                                          tot_registros=0)
            commit()
            print('Processo ativo: %d' % processo_ativo.id)

        tot_files = 0
        tot_erros = 0
        tot_dup = 0
        dest_dir = settings.BASE_DIR + '/data'
        set_autocommit(False)
        processo = Processo(processo_ativo)

        if options['twit'] != 'data':
            filename = join(dest_dir, options['twit'])
            if isfile(filename):
                with open(filename, 'r') as file:
                    texto = file.read()
                    twitter_data = json.loads(texto)
                    tweet, user = processo.load_twitter(twitter_data)
                    if tweet:
                        commit()
                    tot_files = 1
            else:
                print('Arquivo %s não encontrado' % filename)
        else:

            try:
                cached_dir = dest_dir + '/cached'
                if not exists(cached_dir):
                    makedirs(cached_dir)
                for arquivo in os.scandir(dest_dir):

                    if arquivo.name.endswith(".json"):
                        filename = join(dest_dir, arquivo.name)
                        if optimize and isfile(join(cached_dir,arquivo.name)):
                            os.remove(filename)
                            tot_dup += 1
                            if tot_dup % 100 == 0:
                                print(f'Duplicados {tot_dup}')
                            continue

                        try:
                            with open(filename, 'r') as file:
                                texto = file.read()
                                twitter_data = json.loads(texto)

                            if 'data' in twitter_data:
                                for record in twitter_data.get('data'):
                                    processo.load_twitter(record)
                            else:
                                processo.load_twitter(twitter_data)

                            commit()
                            rename(filename, join(cached_dir, arquivo.name))
                        except Exception as e:
                            print('Erro no arquivo %s: %s' % (filename, e))
                            traceback.print_exc()
                            rename(filename, join(dest_dir, 'ruim', arquivo.name))
                            rollback()
                            tot_erros += 1
                        tot_files += 1
            finally:
                if tot_files == 0:
                    if processo_ativo.tot_registros == 0:
                        processo_ativo.delete()
                    print('Nenhum arquivo processado %s' % timezone.now())
                else:
                    processo_ativo.status = Processamento.CONCLUIDO
                    tot_files += (processo_ativo.tot_registros or 0)
                    processo_ativo.tot_registros = tot_files
                    processo_ativo.save()
                commit()
                print('Processamento concluído')

        # Estatísticas
        if len(processo.termos) == 1:
            termo = Termo.objects.filter(id=processo.termos[0]).first()
            processo_ativo.termo = termo
            processo_ativo.save()

        # Atualiza o contador de tweets de cada termo importado
        for termo in Termo.objects.filter(id__in=processo.termos):
            ultima_contagem = termo.last_count
            tweets = termo.tweetinput_set.all().order_by('-tweet')
            if tweets:
                termo.ult_tweet = tweets[0].tweet.twit_id
                termo.last_count = tweets.count()
            termo.save()
            diferenca = termo.last_count - ultima_contagem
            log_message(termo.projeto, f'{diferenca} registros importados no termo {termo.busca}')
        commit()

        if tot_files != 0:
            print('Arquivos processados: %d' % tot_files)
            if optimize:
                print('Arquivos duplicados: %d' % tot_dup)
            print('Termos processados: %d' % len(processo.termos))
            print('Arquivos com erro: %d' % tot_erros)
            print('Novos Usuários: %d' % processo.counter_users)
            print('Novos Tweets: %d' % processo.counter_tweets)
            print('Novos Retweets: %d' % processo.counter_retweets)
