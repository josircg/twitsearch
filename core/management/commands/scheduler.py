# -*- coding: utf-8 -*-
import json
import requests
import pytz

from datetime import datetime
from django.core.management.base import BaseCommand
from twitsearch.settings import TIME_ZONE
from core.models import convert_date, Processamento, PROC_BACKUP, PROC_FECHAMENTO
from core.management.commands.backup_project import export_s3


class Command(BaseCommand):
    label = 'Execute scheduled tasks'
    agora = datetime.now(pytz.timezone(TIME_ZONE))
    header = None
    tot_registros = 0
    tot_updates = 0

    def handle(self, *args, **options):
        for proc in Processamento.objects.filter(status=Processamento.AGENDADO).order_by('dt'):
            if proc.tipo == PROC_BACKUP:
                result = export_s3(proc.termo.projeto)
                if result == 0:
                    proc.status = 'C'
                    proc.save()

        print(f'Total de usuários lidos: {self.tot_registros}')
        print(f'Total de usuários atualizados: {self.tot_updates}')



