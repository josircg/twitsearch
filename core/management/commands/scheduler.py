# -*- coding: utf-8 -*-
import json
import requests
import pytz

from datetime import datetime
from django.core.management.base import BaseCommand
from twitsearch.settings import TIME_ZONE
from core.models import convert_date, Processamento, PROC_BACKUP, PROC_FECHAMENTO
from core.management.commands.backup_project import export_s3
from django.db.transaction import set_autocommit, commit, rollback

class Command(BaseCommand):
    label = 'Execute scheduled tasks'
    agora = datetime.now(pytz.timezone(TIME_ZONE))
    header = None
    tot_registros = 0
    tot_updates = 0

    def handle(self, *args, **options):
        set_autocommit(False)
        for proc in Processamento.objects.filter(status=Processamento.AGENDADO).order_by('dt'):
            if proc.tipo == PROC_BACKUP:
                print('Iniciando Backup do Projeto %s' % proc.termo.projeto.id)
                proc.status = 'P'
                proc.save()
                commit()
                try:
                    result = export_s3(proc.termo.projeto)
                except Exception as e:
                    print('%s' % e)
                    result = -1
                proc.status = 'C' if result == 0 else 'E'
                proc.save()
                commit()



