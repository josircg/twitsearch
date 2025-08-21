# Atualmente o Crawler associa ao projetos os tweets pais de um tweet
#
from django.core.management.base import BaseCommand

from datetime import datetime, timedelta

from core.models import *

from twitsearch.settings import TIME_ZONE
from core.models import Termo

from core.actions import generate_tags_file


class Command(BaseCommand):
    label = 'Remove tweets not related to the query'

    def add_arguments(self, parser):
        parser.add_argument('--termo', type=str, help='Termo ID')

    def handle(self, *args, **options):
        id_termo = options['termo']
        termo = Termo.objects.get(id=id_termo)
        criterio = termo.busca
        if criterio.startswith('from:'):
            user = criterio.split()[0].split(':')[1]
        else:
            user = None
        tot_removidos = 0
        tot_lidos = 0
        for record in TweetInput.objects.filter(termo=termo).select_related('tweet','tweet__user'):
            tot_lidos += 1
            if tot_lidos % 1000 == 0:
                print(tot_lidos)
            if user:
                if record.tweet.user.username != user:
                    record.delete()
                    tot_removidos += 1
            else:
                if record.tweet.text.find(criterio) == -1:
                    record.delete()
                    tot_removidos += 1
        print(f'Total lidos: {tot_lidos}')
        print(f'Total removidos: {tot_removidos}')


