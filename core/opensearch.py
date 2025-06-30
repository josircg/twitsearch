from opensearchpy import OpenSearch
from django.conf import settings


def connect_opensearch(server_alias):
    server = settings.OPENSEARCH_SERVERS[server_alias]
    
    host = server['host']
    port = server['port']
    auth = server['http_auth']

    open_search_client = OpenSearch(
        hosts=[{'host': host, 'port': port}],
        http_compress=True,
        http_auth=auth,
        use_ssl=True,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
        timeout=2000,
        # ca_certs=server['ca_certs_path']
    )
    return open_search_client


def create_if_not_exists_index(client: OpenSearch, index_name):
    index_body = {
        'settings': {
            'index': {
                'number_of_replicas': 2,
                'number_of_shards': 4
            }
        }
    }
    
    try:
        if not client.indices.exists(index=index_name):
            client.indices.create(index=index_name, body=index_body)
    except Exception as e:
        print('Erro na conexão com o Opensearch')
        raise ValueError(e)


def save_object(client: OpenSearch, data, index_name):
    return client.index(
        index=index_name,
        id=data['id'],
        body=data,
        request_timeout=20,
        refresh=True
    )