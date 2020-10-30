# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import json
import pytz
import shlex

from os import scandir, rename, makedirs
from os.path import isfile, join, exists

from twitsearch.settings import BASE_DIR
from core.models import *
from django.utils import timezone
from django.db.transaction import set_autocommit, commit, rollback

# Contador de registros importados
COUNTER = {}
# from typing import Dict, Any - só python 3.6
# COUNTER: Dict[Any, Any] = {}

# Caso o tweet não tenha um processo definido, utilizar o processamento padrão para todos
PROC_PADRAO = None


def find_termo(termo, texto):
    for palavra in termo.upper().split('OR'):
        if palavra.strip() in texto.upper():
            return True
    return False


# https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/intro-to-tweet-json
def process_twitter(src, processo_pai=None):
    global PROC_PADRAO, COUNTER
    try:
        user = TweetUser.objects.get(twit_id=src['user']['id'])
    except TweetUser.DoesNotExist:
        user = TweetUser(twit_id=src['user']['id'],
                     username=src['user']['screen_name'],
                     name=src['user']['name'],
                     location=src['user']['location'],
                     verified=src['user']['verified'],
                     created_at=convert_date(src['user']['created_at']).date())
        user.save()
        COUNTER['users'] += 1

    dt = convert_date(src['created_at'])
    try:
        FollowersHistory.objects.get(user=user, dt=dt)
    except FollowersHistory.DoesNotExist:
        follow = FollowersHistory(user=user, dt=dt,
                                  followers=src['user']['followers_count'],
                                  favourites=src['user']['favourites_count'])
        follow.save()

    follow = FollowersHistory.objects.filter(user=user).latest('dt')
    if user.followers != follow.followers:
        user.followers = follow.followers
        user.save()

    # Se houver um processo fixo, utilizar sempre ele, desprezando o indicado no tweet
    if processo_pai:
        processo = processo_pai
    else:
        if 'process' in src:
            try:
                processo = Processamento.objects.get(id=src['process'])
            except Processamento.DoesNotExist:
                processo = PROC_PADRAO
        else:
            # Se não existe processo no Twitter, utilizar o Processo padrão
            processo = PROC_PADRAO

    # Se o proc é nulo, então ele ainda não foi criado!
    if not processo:
        PROC_PADRAO = Processamento.objects.create(dt=timezone.now())
        PROC_PADRAO.save()
        processo = PROC_PADRAO
        print('Processo default: %d' % processo.id)

    if 'quoted_status' in src:
        tweet = process_twitter(src['quoted_status'], processo)
        retweet, created = Retweet.objects.get_or_create(tweet=tweet, user=user, created_time=dt)
        if created:
            COUNTER['retweets'] += 1
        else:
            retweet.retweet_id = src['id_str']
            retweet.save()

    if 'retweeted_status' in src:
        tweet = process_twitter(src['retweeted_status'], processo)
        retweet, created = Retweet.objects.get_or_create(tweet=tweet, user=user, created_time=dt)
        if created:
            COUNTER['retweets'] += 1
        else:
            retweet.retweet_id = src['id_str']
            retweet.save()
    else:
        if 'full_text' in src:
            texto = src['full_text']
        else:
            texto = src['text']

        termo = processo.termo
        if termo and ('process' not in src) and not find_termo(termo.busca, texto):
            termo = None

        try:
            tweet = Tweet.objects.get(twit_id=src['id_str'])
        except Tweet.DoesNotExist:
            tweet = Tweet(
                        twit_id=src['id_str'], user=user, text=texto,
                        created_time=dt,
                        retweets=0,
                        favorites=0,
                        termo=termo,
                        language=src['lang'])
            COUNTER['tweets'] += 1

        if 'retweet_count' in src:
            tweet.retweets = max(src['retweet_count'], tweet.retweets)
        if 'favorite_count' in src:
            tweet.favorites = max(src['favorite_count'], tweet.favorites)
        tweet.save()

        TweetInput.objects.get_or_create(processamento=processo, tweet=tweet, termo=termo)

    return tweet


class Command(BaseCommand):
    label = 'Importa Tweets'

    def add_arguments(self, parser):
        parser.add_argument('twit', type=str, help='Twitter File',)
        parser.add_argument('-p', '--processo', type=str, help='Processo Default', nargs='?')
        parser.add_argument('-f', '--force', help='Accept multiple imports running', nargs='?')
        parser.add_argument('-x', '--fixo', type=str, help='Processo Fixo')

    def handle(self, *args, **options):
        COUNTER['users'] = 0
        COUNTER['tweets'] = 0
        COUNTER['retweets'] = 0

        force = options.get('force')

        if options['processo']:
            try:
                proc = Processamento.objects.get(id=options['processo'])
            except Processamento.DoesNotExist:
                # Se o processo determinado não foi encontrado, deve-se interromper a rotina
                self.stdout.write(self.style.WARNING('Processo %s não encontrado' % options['processo']))
                return
        else:
            proc = None

        tot_files = 0
        dest_dir = BASE_DIR + '/data'
        set_autocommit(False)
        if options['twit'] != 'data':
            filename = join(dest_dir, options['twit'])
            if isfile(filename):
                with open(filename, 'r') as file:
                    texto = file.read()
                    twit = json.loads(texto)
                process_twitter(twit, proc)
                commit()
                tot_files = 1
            else:
                print('Arquivo %s não encontrado' % filename)
        else:
            if not force:
                if LockProcessamento.objects.filter(locked=True):
                    print('Importação pendente')
                    return
            LockProcessamento.objects.update(locked=True)
            commit()
            try:
                cached_dir = dest_dir + '/cached'
                if not exists(cached_dir):
                    makedirs(cached_dir)
                for arquivo in scandir(dest_dir):
                    if arquivo.name.endswith(".json"):
                        filename = join(dest_dir, arquivo.name)
                        try:
                            with open(filename, 'r') as file:
                                texto = file.read()
                                twit = json.loads(texto)
                            process_twitter(twit)
                            commit()
                            rename(filename, join(cached_dir, arquivo.name))
                        except Exception as e:
                            print('Erro no arquivo %s: %s' % (twit['id_str'], e))
                            # rename(filename, join(dest_dir, 'ruim', arquivo.name))
                            rollback()
                        tot_files += 1
            finally:
                LockProcessamento.objects.update(locked=False)
                commit()

        print('Arquivos processados: %d' % tot_files)
        print('Novos Usuários: %d' % COUNTER['users'])
        print('Novos Tweets: %d' % COUNTER['tweets'])
        print('Novos Retweets: %d' % COUNTER['retweets'])
