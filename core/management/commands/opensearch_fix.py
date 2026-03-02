import re
import string
from collections import Counter

#
# Rotina ainda em desenvolvimento - 2/3/2026
#
from opensearchpy import OpenSearch

from django.core.management.base import BaseCommand

from core.opensearch import connect_opensearch

padrao_re = re.compile(r"[^a-zA-Z0-9\sÁáÀàÂâÉéÊêÍíÓóÚúüÃãÕõÇç-]", re.UNICODE)

def match_query(query: str, text: str) -> bool:
    """
    Verifica se algum termo do query está presente em text.
    Remove parênteses e suporta apenas OR.
    """
    query = re.sub(r'[\\()"]', '', query)
    text = text.lower()
    termos = [t.strip().lower() for t in query.split('OR')]
    return any([t in text for t in termos])

# somente arquivadas
# "query": {"bool": {"must": [{"match": {"arquivada": True}}]}},
#     search_body = {
#         'query': {
#             'match': {
#                 'id': "tw:1441550021019586564"
#             }
#         },
#     }

def get_records(opensearch: OpenSearch, index_name, size=1000, search_after=None):
    search_body = {
        "sort": [ {"_id": {"order": "asc"}} ],
        "size": size
    }

    if search_after:
        search_body["search_after"] = search_after

    response = opensearch.search(index=index_name, body=search_body)
    hits = response["hits"]["hits"]
    results = [hit["_source"] for hit in hits]
    if hits and hits[-1].get('sort'):
        next_search_after = hits[-1]["sort"]
    else:
        next_search_after = None
    return results, next_search_after


class Command(BaseCommand):
    label = 'Fix Opensearch Records'

    def add_arguments(self, parser):
        parser.add_argument('--server', type=str, help='Server')
        parser.add_argument('--index', type=str, help='Index')

    def handle(self, *args, **options):
        conn = connect_opensearch(options.get('server'))
        if not conn.indices.exists(index=options.get('index')):
            print('Índice não encontrado')

        index_name = options.get('index')
        last_search_after = None
        batch_size = 200
        tot_fixed = 0
        tot_read = 0
        while True:
            # busca os registros arquivados
            results, next_search_after = get_records(conn, index_name, batch_size, last_search_after)
            last_search_after = next_search_after
            num_results = len(results)
            print(f"Registros lidos: {tot_read}")

            for row in results:
                tot_read += 1

                if tot_read < 4000:
                    continue

                if not 'busca' in row:
                    continue

                busca = row['busca']
                conteudo = row['conteudo']
                hashtags = re.findall(r'#\w+', conteudo)
                mencoes = re.findall(r'@\w+', conteudo)
                links = re.findall(r'https?://\S+|www\.\S+', conteudo)

                # deixa a lista de palavras sem os links e as hashtags
                stopwords = links + hashtags + mencoes
                palavras = ' '.join([x.lower() for x in conteudo.split() if x not in stopwords])
                # remove pontuações nas palavras
                palavras = padrao_re.sub('', palavras).split()
                # remove números
                palavras = [x for x in palavras if len(re.sub(r'[0-9]', '', x)) > 0]
                # remove letras soltas e pontuações
                palavras = [x for x in palavras if len(re.sub(r'[^\w\s]', '', x)) > 1]

                s = []
                unicos = []
                for item in Counter(palavras).most_common():
                    s.append(f'{item[0]} ({item[1]})')
                    unicos.append(item[0])
                termos_agrupados = ','.join(s)
                termos_unicos = ','.join(unicos)

                conteudo = conteudo.lower()
                termos = re.sub(r'[\\()"]', '', busca)
                termos = [t.strip().lower() for t in termos.split('OR')]
                termos = [x for x in termos if x in conteudo]
                arquivada = len(termos) == 0
                if arquivada != row['arquivada']:
                    row['arquivada'] = arquivada
                    tot_fixed += 1
                row['termos'] = termos
                row["termos_unicos"] = termos_unicos
                row["termosAgrupados"] = termos_agrupados
                conn.index(
                    index=index_name,
                    body=row,
                    id=row['id'],
                    request_timeout=200)

            if num_results < batch_size:
                break

        print(f'Registros lidos: {tot_read}')
        print(f'Registros corrigidos: {tot_fixed}')

