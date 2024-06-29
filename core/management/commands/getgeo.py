import os
import json

from django.db.transaction import set_autocommit, commit
from django.core.management.base import BaseCommand
from twitsearch.settings import BASE_DIR
from core.models import *


class Command(BaseCommand):
    label = 'Update Twitter Language and Geo Location'

    def handle(self, *args, **options):

        tot_files = 0
        tot_notfound = 0
        dest_dir = BASE_DIR + '/data/cached'
        set_autocommit(False)
        for root, dirs, files in os.walk(dest_dir, topdown=True):
            tot_files += 1
            print(files)
            with open(files, 'r') as file:
                texto = file.read()
                twit = json.loads(texto)
            if 'location' in twit:
                tweets = Tweet.objects.filter(id=twit['id_str'])
                if tweets.count() > 0:
                    if tweets[0].location != twit['location']:
                        tweets[0].location = twit['location']
                        tweets[0].save()
                else:
                    if twit['retweeted_status'] and 'location' in twit['retweeted_status']:
                        tweets = Tweet.objects.filter(twit_id=twit['retweeted_status']['id_str'])
                        if tweets.count() > 0:
                            tweets[0].location = twit['retweeted_status']['location']
                            tweets.save()
                if tot_files % 100 == 0:
                    print(tot_files)
                    commit()
            else:
                tot_notfound += 1

        print('Arquivos processados: %d' % tot_files)
        print('Arquivos não encontrados: %d' % tot_notfound)
