from django.core.management.base import BaseCommand
from django.db import transaction

import openpyxl

from telegram.models import Canal, Categoria


class Command(BaseCommand):
    help = 'Carrega/atualiza Canais a partir da planilha class_canais_news_media.xlsx (aba Página1)'

    def add_arguments(self, parser):
        parser.add_argument(
            'arquivo',
            nargs='?'            
        )

    def handle(self, *args, **options):
        arquivo = options['arquivo']

        wb = openpyxl.load_workbook(arquivo, data_only=True)
        ws = wb['Página1']

        canais_criados = 0
        canais_existentes = 0
        categorias_criadas = 0
        linhas_sem_username = 0

        categorias_cache = {}

        rows = ws.iter_rows(min_row=2, values_only=True)

        with transaction.atomic():
            for row in rows:
                if not row:
                    linhas_sem_username += 1
                    continue

                username_raw = row[0]
                classification_raw = row[1] if len(row) > 1 else None

                username = (username_raw or '').strip() if isinstance(username_raw, str) else (
                    str(username_raw).strip() if username_raw is not None else ''
                )

                if not username:
                    linhas_sem_username += 1
                    continue

                canal, created = Canal.objects.get_or_create(
                    username=username,
                    defaults={'status': Canal.Status.ATIVO},
                )
                if created:
                    canais_criados += 1
                else:
                    canais_existentes += 1

                classification = None
                if isinstance(classification_raw, str):
                    classification = classification_raw.strip()
                elif classification_raw is not None:
                    classification = str(classification_raw).strip()

                if classification:
                    categoria = categorias_cache.get(classification)
                    if categoria is None:
                        categoria, cat_created = Categoria.objects.get_or_create(nome=classification)
                        categorias_cache[classification] = categoria
                        if cat_created:
                            categorias_criadas += 1

                    if not canal.categorias.filter(pk=categoria.pk).exists():
                        canal.categorias.add(categoria)

        self.stdout.write(self.style.SUCCESS('Carga concluída.'))
        self.stdout.write(f'Canais criados: {canais_criados}')
        self.stdout.write(f'Canais já existentes: {canais_existentes}')
        self.stdout.write(f'Categorias criadas: {categorias_criadas}')
        self.stdout.write(f'Linhas sem username (puladas): {linhas_sem_username}')
