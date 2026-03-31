
import os
import json
import time
import uuid

from opensearchpy import helpers
from django.conf import settings
from django.core.management.base import BaseCommand

from core.opensearch import connect_opensearch, create_if_not_exists_index


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
                with open(entrada.path, 'r', encoding='utf-8') as f:
                    registro = json.load(f)
                    if 'created_at' in registro:
                         del registro['created_at']
                    if 'id' in registro:
                        registro['id'] = str(registro['id'])
                    if 'user' in registro:
                        if 'id' in registro['user']:
                            registro['user']['id'] = str(registro['user']['id'])
                        if 'created_at' in registro['user']:
                             del registro['user']['created_at']

                    dados_na_memoria.append(registro)
                    contador += 1

                    # Opcional: Log de progresso a cada 100 arquivos
                    if contador % 100 == 0:
                        print(f"Lidos {contador} arquivos...", end='\r')


    end_load = time.time()
    print(f"\nConcluído: {len(dados_na_memoria)} arquivos carregados em {end_load - start_load:.2f}s.")
    return dados_na_memoria


def get_disk_stats(client):
    """Captura as estatísticas de escrita de todos os nós."""
    stats = client.nodes.stats(metric="fs")
    nodes_data = {}
    for node_id, data in stats['nodes'].items():
        # Focamos no dispositivo rbd0 (ou no primeiro disponível)
        device = data['fs']['io_stats']['devices'][0]
        nodes_data[node_id] = {
            "name": data['name'],
            "writes": device['write_operations'],
            "write_ms": device['write_time']
        }
    return nodes_data


def executar_benchmark_com_io(client, nome_indice, lista_docs, lote_tamanho=200):
    if not lista_docs: return

    print(f"\n--- Iniciando Stress Test (Lote: {len(lista_docs)}/{lote_tamanho}) ---")

    # 1. Captura estado inicial do disco
    stats_inicio = get_disk_stats(client)

    actions = [{"_op_type": "index", "_id": str(uuid.uuid4()), "_index": nome_indice, "_source": doc} for doc in lista_docs]
    start_time = time.time()

    # 2. Executa a carga
    sucesso, _ = helpers.bulk(client, actions, chunk_size=lote_tamanho, request_timeout=120)

    end_time = time.time()

    # 3. Captura estado final do disco
    stats_fim = get_disk_stats(client)

    # 4. Cálculos de Performance
    duracao = end_time - start_time
    print("\n" + "=" * 60)
    print(f"MÉTRICAS DE APLICAÇÃO (Python -> Rede -> OpenSearch):")
    print(f"Velocidade: {len(lista_docs) / duracao:.2f} docs/s | Tempo: {duracao:.2f}s")
    print("=" * 60)
    print(f"MÉTRICAS DE INFRAESTRUTURA (Latência de Disco por Nó):")

    for n_id in stats_inicio:
        # Delta de operações e tempo
        d_writes = stats_fim[n_id]['writes'] - stats_inicio[n_id]['writes']
        d_ms = stats_fim[n_id]['write_ms'] - stats_inicio[n_id]['write_ms']

        # Cálculo da latência média de escrita durante este teste
        # Fórmula: Latência = Tempo Total de Escrita / Número de Operações
        latencia_io = d_ms / d_writes if d_writes > 0 else 0

        status_disco = "🔴 CRÍTICO" if latencia_io > 100 else "🟡 LENTO" if latencia_io > 20 else "🟢 OK"

        print(f"Nó: {stats_inicio[n_id]['name']:<25} | Latência I/O: {latencia_io:>7.2f} ms/op | {status_disco}")
    print("=" * 60)


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
            create_if_not_exists_index(conn, options.get('index'))

            dest_dir = settings.BASE_DIR + '/data/cached'
            info = carregar_dados_da_pasta(dest_dir, 20)
            if len(info) == 0:
                print(f"Nenhum arquivo JSON encontrado em: {dest_dir}")
                return

            executar_benchmark_com_io(conn, options.get('index'), info)
