from django.core.management.base import BaseCommand

from core.apps import connect_postgresql


class Command(BaseCommand):
    label = 'Teste PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument('--server', type=str, help='Server')

    def handle(self, *args, **options):
        pg = connect_postgresql(options.get('server'))
        if pg:
            with pg.cursor() as cursor:
                cursor.execute("SELECT version();")
                record = cursor.fetchone()
                print(f"Connected: {record[0]}")



