import psycopg2 as psycopg

from django.conf import settings
from django.core.management.base import BaseCommand


def connect_postgresql(server_alias: str):
    server = settings.PG_SERVERS.get(server_alias)
    if not server:
        raise Exception(f'Entrada "{server_alias}" não encontrada')
    host = server['host']
    port = server.get('port', 5432)
    database = server['database']
    username = server['username']
    password = server['password']
    pg = psycopg.connect(f"dbname={database} user={username} password={password} host={host} port={port}")
    return pg


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



