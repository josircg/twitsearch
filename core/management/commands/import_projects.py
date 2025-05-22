import os
import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Projeto, Termo, Rede, PROC_PREMIUM
from datetime import datetime

class Command(BaseCommand):
    help = 'Importa projetos e termos de um arquivo CSV'

    def handle(self, *args, **options):
        # Configurações fixas
        DT_INICIAL = datetime(year=2025, month=5, day=22, hour=0, minute=0)
        REDES_IDS = [2, 3, 4]  # Twitter, Youtube, Telegram
        USUARIO_PADRAO_ID = 1  # Modificar conforme necessário

        # Caminho do arquivo
        csv_path = os.path.join(os.getcwd(), 'eixos_temas.csv')

        try:
            with open(csv_path, 'r', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file)
                
                with transaction.atomic():
                    for row in reader:
                        # Processar projeto
                        projeto, created = Projeto.objects.get_or_create(
                            nome=row['Eixo FDD'],
                            defaults={
                                'usuario_id': USUARIO_PADRAO_ID,
                                'alcance': 0,
                                'status': 'A'
                            }
                        )

                        # Adicionar redes para novos projetos
                        if created:
                            for rede_id in REDES_IDS:
                                rede, _ = Rede.objects.get_or_create(id=rede_id)
                                projeto.redes.add(rede)

                        # Processar termo
                        if not Termo.objects.filter(projeto=projeto, busca=row['Query']).exists():
                            Termo.objects.create(
                                projeto=projeto,
                                busca=row['Query'].replace('""','"'),
                                descritivo=row['Tema'],
                                dtinicio=DT_INICIAL,
                                tipo_busca=PROC_PREMIUM,  
                                status='A',
                                last_count=0,
                                estimativa=0
                            )

            self.stdout.write(self.style.SUCCESS('Importação concluída com sucesso'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('Arquivo CSV não encontrado'))
