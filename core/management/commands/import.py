# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import json
from shlex import split as splitx

from os import scandir, rename, makedirs
from os.path import isfile, join, exists

from twitsearch.settings import BASE_DIR
from core.models import *
from django.db.transaction import set_autocommit, commit, rollback

# from typing import Dict, Any - só python 3.6
# COUNTER: Dict[Any, Any] = {}
COUNTER = {}


def find_termo(termo, texto):
    for palavra in termo.upper().splitx('OR'):
        if palavra.strip() in texto.upper():
            return True
    return False


# https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/intro-to-tweet-json
def process_twitter(src):
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

    # Se existir processo no twitter, tentar achar ele. Se não achar, assumir o padrão
    if not COUNTER['fixo']:
        if 'process' in src and src['process'] != COUNTER.get('proc'):
            try:
                COUNTER['proc'] = Processamento.objects.get(id=src['process'])
                termo = COUNTER['proc'].termo
            except Processamento.DoesNotExist:
                COUNTER['proc'] = COUNTER.get('novo')
                print('Processamento não encontrado: %d' % src['process'])
        else:
            # Se não existe processo no Twitter, utilizar o Processo padrão
            COUNTER['proc'] = COUNTER['fixo']

        # Se o proc é nulo, então ele ainda não foi criado!
        if not COUNTER['proc']:
            COUNTER['novo'] = Processamento.objects.create(dt=datetime.today())
            COUNTER['proc'] = COUNTER['novo']
            termo = None

    if 'quoted_status' in src:
        if termo and find_termo(termo.busca, src['quoted_status']['full_text']):
            tweet = process_twitter(src['quoted_status'])
            retweet, created = Retweet.objects.get_or_create(tweet=tweet, user=user, created_time=dt)
            if created:
                COUNTER['retweets'] += 1
            else:
                retweet.retweet_id = src['id_str']
                retweet.save()

    if 'retweeted_status' in src:
        tweet = process_twitter(src['retweeted_status'])
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

        if COUNTER['proc']:
            TweetInput.objects.get_or_create(processamento=COUNTER['proc'], tweet=tweet)

        if 'retweet_count' in src:
            tweet.retweets = max(src['retweet_count'], tweet.retweets)
        if 'favorite_count' in src:
            tweet.favorites = max(src['favorite_count'], tweet.favorites)
        tweet.save()
    return tweet


class Command(BaseCommand):
    label = 'Importa Tweets'

    def add_arguments(self, parser):
        parser.add_argument('twit', type=str, help='Twitter File',)
        parser.add_argument('-p', '--processo', type=str, help='Processo Default', nargs='?')
        parser.add_argument('-f', '--fixo', type=str, help='Processo Fixo')

    def handle(self, *args, **options):
        COUNTER['users'] = 0
        COUNTER['tweets'] = 0
        COUNTER['retweets'] = 0

        if options['processo']:
            try:
                proc = Processamento.objects.get(id=options['processo'])
                COUNTER['proc'] = proc
                COUNTER['fixo'] = True
            except Processamento.DoesNotExist:
                # Se o processo determinado não foi encontrado, deve-se interromper a rotina
                self.stdout.write(self.style.WARNING('Processo %s não encontrado' % options['processo']))
                return
        else:
            COUNTER['fixo'] = False

        tot_files = 0
        dest_dir = BASE_DIR + '/data'
        set_autocommit(False)
        if options['twit'] != 'data':
            filename = join(dest_dir, options['twit'])
            if isfile(filename):
                with open(filename, 'r') as file:
                    texto = file.read()
                    twit = json.loads(texto)
                process_twitter(twit)
                commit()
                tot_files = 1
            else:
                print('Arquivo %s não encontrado' % filename)
        else:
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
