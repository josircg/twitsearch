from django.conf import settings
from django.core.management.base import BaseCommand

from core.opensearch import connect_opensearch

class Command(BaseCommand):
    label = 'Generate csv tags file'

    def add_arguments(self, parser):
        parser.add_argument('--server', type=str, help='Server')
        parser.add_argument('--index', type=str, help='Index')

    def handle(self, *args, **options):
        conn = connect_opensearch(options.get('server'))
        info = conn.info()
        if info:
            print(info)
        else:
            print('Erro na Conexão')

        if conn.indices.exists(index=options.get('index')):
            print('Conexão realizada')
        else:
            print('Índice não encontrado')
