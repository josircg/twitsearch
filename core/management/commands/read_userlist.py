# -*- coding: utf-8 -*-
import os
import pytz
import csv

from datetime import datetime
from django.core.management.base import BaseCommand
from twitsearch.settings import TIME_ZONE, BASE_DIR
from core.models import Projeto, Termo, PROC_PREMIUM

class Command(BaseCommand):
    label = 'Get User data'
    agora = datetime.now(pytz.timezone(TIME_ZONE))
    header = None
    tot_registros = 0
    tot_updates = 0

    def add_arguments(self, parser):
        parser.add_argument('-p', '--project', type=str, help='ID Projeto', nargs='?')

    def handle(self, *args, **options):

        projeto_id = options['project']
        projeto = Projeto.objects.filter(id=projeto_id).first()
        if not projeto:
            print(f'Projeto {projeto_id} não encontrado')
            return

        dt_inicial = datetime(year=2022, month=1, day=1, hour=0, minute=0)
        dt_final = datetime(year=2022, month=3, day=1, hour=0, minute=0)

        filename = os.path.join(BASE_DIR, 'media', 'csv', 'userlist.csv')
        csv_file = open(filename,'r')
        reader = csv.reader(csv_file, delimiter=',')
        next(reader, None)
        user_list = ''
        for user in reader:
            user_list += 'from:%s OR ' % user[0]
            self.tot_registros += 1
            if self.tot_registros % 4 == 0:
                user_list = user_list[:-4]
                Termo.objects.create(projeto_id=projeto_id, busca=user_list,
                                     dtinicio=dt_inicial, dtfinal=dt_final,
                                     tipo_busca=PROC_PREMIUM, status='A')
                user_list = ''
            if self.tot_registros % 200 == 0:
                print(self.tot_registros)

        if len(user_list) > 0:
            Termo.objects.create(projeto_id=projeto_id, busca=user_list,
                                 dtinicio=dt_inicial, dtfinal=dt_final,
                                 tipo_busca=PROC_PREMIUM, status='A')

        print(f'Total de usuários lidos: {self.tot_registros}')



