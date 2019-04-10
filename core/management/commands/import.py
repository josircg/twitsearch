# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import json

from os import scandir, rename, makedirs
from os.path import isfile, join, exists

from twitsearch.settings import BASE_DIR
from core.models import *
from django.db.transaction import set_autocommit, commit

# from typing import Dict, Any - só python 3.6
# COUNTER: Dict[Any, Any] = {}
COUNTER = {}


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

    if 'process' in src and src['process'] != COUNTER['proc_id']:
        COUNTER['proc'] = Processamento.objects.get(id=src['process'])
        COUNTER['proc_id'] = COUNTER['proc'].id

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
                    termo=COUNTER['proc'].termo)
        COUNTER['twits'] += 1
    tweet.retweets = max(src['retweet_count'], tweet.retweets)
    tweet.favorites = max(src['favorite_count'], tweet.favorites)
    if 'retweeted_status' in src:
        tweet.retwit_id = src['retweeted_status']['id']
    tweet.save()

    TweetInput.objects.create(processamento=COUNTER['proc'], tweet=tweet)

    if 'retweeted_status' in src:
        process_twitter(src['retweeted_status'])


class Command(BaseCommand):
    label = 'Converte Twits'

    def add_arguments(self, parser):
        parser.add_argument('twit', type=str, help='Twitter File',)
        parser.add_argument('-p', '--processo', type=str, help='Processo Default')

    def handle(self, *args, **options):
        COUNTER['users'] = 0
        COUNTER['twits'] = 0
        COUNTER['proc_id'] = 0
        if 'processo' in options:
            try:
                proc = Processamento.objects.get(id=options['processo'])
                COUNTER['proc'] = proc
                COUNTER['proc_id'] = proc.id
            except Processamento.DoesNotExist:
                self.stdout.write(self.style.WARNING('Processo %s não encontrado' % options['processo']))
                return
        else:
            self.stdout.write(self.style.WARNING('ID do Processo é obrigatório'))
            return

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
            cached_dir = dest_dir + '/cached'
            if not exists(cached_dir):
                makedirs(cached_dir)
            for arquivo in scandir(dest_dir):
                if arquivo.name.endswith(".json"):
                    filename = join(dest_dir, arquivo.name)
                    with open(filename, 'r') as file:
                        texto = file.read()
                        twit = json.loads(texto)
                    process_twitter(twit)
                    commit()
                    rename(filename, join(cached_dir, arquivo.name))
                    tot_files += 1

        print('Arquivos processados: %d' % tot_files)
        print('Novos Usuários: %d' % COUNTER['users'])
        print('Novos Twits: %d' % COUNTER['twits'])
