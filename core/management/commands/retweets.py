from django.utils import timezone

from django.db import connection
from django.core.management.base import BaseCommand

from core.models import *
from django.db.transaction import set_autocommit, commit

#
# Rotinas de Ajuste da Base
#

# Para cada tweet que tenha um pai, cria o retweet e apaga o tweet original
def remove_retweets():
    tot_files = 0
    set_autocommit(False)
    dset = Tweet.objects.filter(retwit_id__isnull=False)
    for tweet in dset:
        try:
            original = Tweet.objects.get(twit_id=tweet.retwit_id)
            Retweet.objects.get_or_create(tweet=original, user=tweet.user, created_time=tweet.created_time,
                                          retweet_id=tweet.twit_id)
            if original.text == tweet.text:
                tweet.delete()
            if tot_files % 100 == 0:
                commit()
            tot_files += 1
            if tot_files % 1000 == 0:
                print(tot_files)
        except Tweet.DoesNotExist:
            print('Tweet Original not found: %s' % tweet.retwit_id)
    commit()
    print('ReTweets processados: %d' % tot_files)


class Command(BaseCommand):
    label = 'Rotinas de Apoio'

    def handle(self, *args, **options):

        hoje = timezone.now()
        proc = Processamento.objects.create(tipo=PROC_MATCH,dt=hoje)
        tot_lidos = 0
        tot_incluidos = 0
        for tweet in Tweet.objects.filter(termo__isnull=False):
            tot_lidos += 1
            _, created = TweetInput.objects.get_or_create(tweet=tweet, termo=tweet.termo,
                                                          defaults={'processamento': proc})
            if created:
                tot_incluidos += 1
            if tot_lidos % 200:
                commit()

        proc.tot_registros = tot_incluidos
        proc.save()
        commit()
        print(f'Registros Lidos {tot_lidos}')
        print(f'Registros criados {tot_incluidos}')
