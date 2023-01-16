# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from datetime import datetime, timedelta

from core.models import *

from twitsearch.settings import TIME_ZONE
from core.models import Termo


def ressurect_termos():
    umahora_atras = datetime.now(pytz.timezone(TIME_ZONE)) - timedelta(hours=1)
    termos = Termo.objects.filter(status__in=('P', 'E'), dtinicio__lt=umahora_atras)
    cnt = 0
    for termo in termos:
        print(termo)
        termo.status = 'A'
        ultimo = termo.tweet_set.order_by('twit_id').first()
        termo.ult_tweet = ultimo.twit_id
        termo.ult_processamento = ultimo.created_time
        termo.last_count = termo.tot_twits
        termo.save()
        cnt += 1
    print('Revived: %d' % cnt)


def ressurect_processamentos():
    grace_time = datetime.now(pytz.timezone(TIME_ZONE)) - timedelta(hours=4)
    Processamento.objects.filter(status__in=('P', 'E'), dt=grace_time).update(status='A')



class Command(BaseCommand):
    label = 'Revive stalled processes'

    def handle(self, *args, **options):
        ressurect_termos()
        ressurect_processamentos()
        # Atualiza os contadores dos termos já concluídos
        cnt = 0
        for termo in Termo.objects.filter(status='C'):
            if termo.last_count != termo.tot_twits:
                termo.last_count = termo.tot_twits
                cnt += 1
                termo.save()
        print('Recounted: %d' % cnt)

        return
