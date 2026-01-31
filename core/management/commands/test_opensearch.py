from django.conf import settings
from django.core.management.base import BaseCommand

from core.opensearch import connect_opensearch

class Command(BaseCommand):
    label = 'Test Opensearch connection'

    def add_arguments(self, parser):
        parser.add_argument('--server', type=str, help='Server')
        parser.add_argument('--index', type=str, help='Index')

    def handle(self, *args, **options):
        server_alias = options.get('server')
        conn = connect_opensearch(server_alias)
        if not conn:
            print('Failed to connect to OpenSearch')

        try:
            info = conn.info()
            if info:
                print(info)
        except:
            print('Sem acesso de monitoramento')

        if options.get('index'):
            if conn.indices.exists(index=options.get('index')):
                server = settings.OPENSEARCH_SERVERS[server_alias]
                print(f"Host: {server['host']} Port: {server['port']}")
                print('Conexão realizada com sucesso')
            else:
                print('Índice não encontrado')
