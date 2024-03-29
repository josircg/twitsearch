# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import json

from os.path import isfile, join

from twitsearch.settings import BASE_DIR
from core.models import *
from django.db.transaction import set_autocommit, commit


class Command(BaseCommand):
    label = 'Update Twitter Language'

    def add_arguments(self, parser):
        parser.add_argument('-t', '--twit', type=str, help='Twitter File',)

    def handle(self, *args, **options):

        if options['twit']:
            dset = Tweet.objects.filter(twit_id=options['twit'])
        else:
            dset = Tweet.objects.filter(language__isnull=True)

        tot_files = 0
        tot_notfound = 0
        dest_dir = BASE_DIR + '/data/cached'
        set_autocommit(False)
        for tweet in dset:
            filename = join(dest_dir, tweet.twit_id+'.json')
            if isfile(filename):
                with open(filename, 'r') as file:
                    texto = file.read()
                    twit = json.loads(texto)
                tweet.language = twit['lang']
                tweet.save()
                if twit['retweeted_status']:
                    original_tweet = Tweet.objects.filter(twit_id=twit['retweeted_status']['id_str'])
                    if original_tweet.count() > 0:
                        original_tweet[0].language = twit['retweeted_status']['lang']
                        original_tweet.save()
                tot_files += 1
                if tot_files % 100 == 0:
                    print(tot_files)
                    commit()
            else:
                tot_notfound +=1
                if tot_notfound % 1000 == 0:
                    print('Arquivo %s não encontrado' % filename)

        print('Arquivos processados: %d' % tot_files)
        print('Arquivos não encontrados: %d' % tot_notfound)
