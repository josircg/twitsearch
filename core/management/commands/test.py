# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db.transaction import set_autocommit, commit
from core.models import Termo

class Command(BaseCommand):
    label = 'Grab Twitters'

    def handle(self, *args, **options):
        set_autocommit(False)
        termos = Termo.objects.filter(id=1)
        termos[0].status = 'P'
        termos[0].save()
        commit()
        input('Aguardando')