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
                commit()
                tot_files += 1
            else:
                print('Arquivo %s não encontrado' % filename)

        print('Arquivos processados: %d' % tot_files)
