import time
import sys
import os

from opensearchpy import helpers
from django.conf import settings
from django.core.management.base import BaseCommand

from core.opensearch import connect_opensearch

import os
import json
import time


def carregar_dados_da_pasta(pasta_origem, limite=500):
    """
    Usa os.scandir para evitar carregar a lista completa de arquivos na RAM.
    Para o processamento assim que atingir o limite.
    """
    print(f"--- Etapa 1: Carregando no máximo {limite} arquivos (Otimizado) ---")
    start_load = time.time()

    dados_na_memoria = []
    contador = 0

    # os.scandir é um gerador, não carrega tudo de uma vez
    with os.scandir(pasta_origem) as entradas:
        for entrada in entradas:
            # Verifica se atingiu o limite solicitado
            if contador >= limite:
                break

            # Verifica se é um ficheiro JSON
            if entrada.is_file() and entrada.name.endswith('.json'):
                try:
                    with open(entrada.path, 'r', encoding='utf-8') as f:
                        dados_na_memoria.append(json.load(f))
                        contador += 1

                        # Opcional: Log de progresso a cada 100 arquivos
                        if contador % 100 == 0:
                            print(f"Lidos {contador} arquivos...", end='\r')

                except Exception as e:
                    print(f"\nErro ao ler {entrada.name}: {e}")

    end_load = time.time()
    print(f"\nConcluído: {len(dados_na_memoria)} arquivos carregados em {end_load - start_load:.2f}s.")
    return dados_na_memoria


def medir_velocidade_gravacao(client, index_name, dados, batch_size=500):
    print(f"--- Iniciando Benchmark de Gravação no índice: {index_name} ---")

    total_docs = len(dados)
    start_time = time.time()

    # Preparar as ações para o bulk
    actions = [
        {
            "_op_type": "index",
            "_index": index_name,
            "_source": doc
        }
        for doc in dados
    ]

    print(f"Enviando {total_docs} documentos em lotes de {batch_size}...")

    # Executar a gravação usando helpers.bulk
    sucesso, erros = helpers.bulk(
        client,
        actions,
        chunk_size=batch_size,
        request_timeout=60
    )

    end_time = time.time()
    duracao_total = end_time - start_time

    # Cálculos de Performance
    docs_por_segundo = total_docs / duracao_total
    tempo_por_doc_ms = (duracao_total / total_docs) * 1000

    print("-" * 50)
    print(f"RESULTADOS:")
    print(f"Tempo Total: {duracao_total:.2f} segundos")
    print(f"Documentos Gravados: {sucesso}")
    print(f"Erros: {len(erros) if isinstance(erros, list) else 0}")
    print(f"Velocidade Média: {docs_por_segundo:.2f} docs/s")
    print(f"Latência Média por Doc: {tempo_por_doc_ms:.2f} ms")
    print("-" * 50)


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
                print('Conexão realizada com sucesso')

            else:
                print('Índice não encontrado')

            dest_dir = settings.BASE_DIR + '/data/cached'
            info = carregar_dados_da_pasta(dest_dir, 10)
            if len(info) == 0:
                print(f"Nenhum arquivo JSON encontrado em: {dest_dir}")
                return
            medir_velocidade_gravacao(conn, options.get('index'), info)
