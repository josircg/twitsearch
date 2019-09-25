# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from datetime import datetime, timedelta

from core.models import *

from twitsearch.settings import TIME_ZONE
from core.models import Termo


class Command(BaseCommand):
    label = 'Revive stalled processes'

    def handle(self, *args, **options):
        umahora_atras = datetime.now(pytz.timezone(TIME_ZONE)) - timedelta(hours=1)
        termos = Termo.objects.filter(status='P', dtinicio__lt=umahora_atras)
        cnt = termos.count()
        termos.update(status='A')
        print('Revived: %d' % cnt)
        return
