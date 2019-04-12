# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db.transaction import set_autocommit, commit
from core.models import Termo

class Command(BaseCommand):
    label = 'Teste Concorrência'

    def handle(self, *args, **options):
        Termo.objects.get(id=1).update(status='P')
        status = 'A'
        while status != 'C':
            status = Termo.objects.get(id=1).status
        print('Concluído!')

