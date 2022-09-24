# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from datetime import datetime, timedelta

from core.models import *

from twitsearch.settings import TIME_ZONE
from core.models import Termo


class Command(BaseCommand):
    label = 'Revive stalled processes'

    def handle(self, *args, **options):
        umahora_atras = datetime.now(pytz.timezone(TIME_ZONE)) - timedelta(hours=0)
        termos = Termo.objects.filter(status='P', dtinicio__lt=umahora_atras)
        cnt = 0
        for termo in termos:
            print(termo)
            termo.status = 'A'
            ultimo = termo.tweet_set.order_by('-twit_id').first()
            termo.ult_tweet = ultimo.twit_id
            termo.ult_processamento = ultimo.created_time
            termo.last_count = termo.tot_twits
            termo.save()
            cnt += 1

        print('Revived: %d' % cnt)
        return
