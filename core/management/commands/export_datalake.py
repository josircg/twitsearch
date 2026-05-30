# Exporta os dados da pasta cached para o Datalake no PostgreSQL
# A rotina de captura do vtrack vai passar a buscar os dados do Datalake e não mais do Opensearch
# Josir - 05/2026
#

import json
import os
from itertools import islice

from os.path import join, exists

import psycopg2 as psycopg

from django.conf import settings
from django.core.management.base import BaseCommand

from core.apps import get_management_logger

logger = get_management_logger("export_datalake")


def connect_postgresql(server_alias: str):
    server = settings.PG_SERVERS.get(server_alias)
    if not server:
        raise Exception(f'Entrada {server_alias} não encontrada')
    host = server['host']
    port = server.get('port', 5432)
    database = server['database']
    username = server['username']
    password = server['password']
    pg = psycopg.connect(f"dbname={database} user={username} password={password} host={host} port={port}")
    return pg


class Processo:

    def __init__(self, pg_server, batch_size=500, queue: bool = True):
        self.pg_client = connect_postgresql(pg_server)
        self.counter_tweets = 0
        self.termos_processados = {}
        self.batch_size = batch_size
        self.queue = queue
        with self.pg_client.cursor() as cursor:
            cursor.execute("SELECT version();")
            record = cursor.fetchone()
            print(f"Connected: {record[0]}")
            sql_insert = "INSERT INTO processo (provenance) VALUES (%s) RETURNING id;"
            cursor.execute(sql_insert, ('capitu',))
            self.processo_id = cursor.fetchone()[0]
        self.pg_client.commit()
        self.batch = {}
        self.arquivos = []

    def insere_docs(self, content: dict):
        tot_lidos = 0
        docs = content if isinstance(content, list) else [content]
        for doc in docs:
            tot_lidos += 1
            doc_id = str(doc.get('id'))
            if doc_id:
                json_str = json.dumps(doc)
                self.batch[doc_id] = json_str.replace('\\u0000', '')
        return tot_lidos

    def commit(self):
        """
        Caso o tweet já exista, move o antigo para o histórico (mantendo o batch_id antigo)
        e insere o novo com o batch_id atual. Também inclui os tweets relevantes na fila para processamento pelo Mage
        """
        cursor = self.pg_client.cursor()
        batch_keys = list(self.batch.keys())
        batch_values = list(self.batch.values())
        # 1. Move o que já existe para o histórico antes de deletar
        sql = f"""
        WITH deleted_rows AS (
            DELETE FROM twitter
            WHERE id = ANY(%s)
            RETURNING id, source, processo
        )
        INSERT INTO historico (id, source, processo)
        SELECT id, source, processo FROM deleted_rows;
        """
        cursor.execute(sql, (batch_keys,))

        # 2. Insere os novos registros com o ID do lote atual
        sql_insert = f"""
        INSERT INTO twitter (id, source, processo)
        SELECT unnest_id, unnest_source::jsonb, %s
        FROM unnest(%s::text[], %s::text[]) AS t(unnest_id, unnest_source);
        """
        cursor.execute(sql_insert, (self.processo_id, batch_keys, batch_values))

        if self.queue:
            # Os tweets que não tiverem termo associado não entram na fila de processamento
            relevantes = []
            for record in batch_values:
                d_record = json.loads(record)
                if d_record.get('termo'):
                    relevantes.append(record)

            sql_insert = f"""
            INSERT INTO fila_twitter (processo, source) SELECT %s, unnest_source::jsonb 
              FROM unnest(%s::text[]) AS t(unnest_source);
            """
            cursor.execute(sql_insert, (self.processo_id, relevantes,))

        self.pg_client.commit()
        self.batch = {}
        # Exclui os arquivos que foram processados
        for arquivo in self.arquivos:
            os.remove(arquivo)
        self.arquivos = []
        return len(relevantes)


class Command(BaseCommand):
    label = 'Importa Tweets'

    def add_arguments(self, parser):
        parser.add_argument('-e', '--estimate', action='store_true',
                            help='Estima número de registros a procesar')
        parser.add_argument('-d', '--source_dir', type=str, nargs='?',
                            help='which folder to read files')
        parser.add_argument('-a', '--archive', action='store_true',
                            help='Records will be archived only and will not be added to Opensearch')

    def handle(self, *args, **options):

        tot_files = 0
        tot_erros = 0
        tot_fila = 0
        tot_registros = 0
        estimate = options.get('estimate')
        archive = options.get('archive')
        dest_dir = options.get('source_dir') or 'queue'
        dest_dir = os.path.join(settings.BASE_DIR, 'data', dest_dir)
        print(dest_dir)
        if archive:
            print('Archive mode')
        processo = Processo('pg_baoba', 500, not archive)

        with os.scandir(dest_dir) as it:
            primeiros_arquivos = islice(it, 50000)
            for arquivo in primeiros_arquivos:
                if arquivo.name.endswith(".json"):
                    try:
                        tot_files += 1
                        if tot_files % 1000 == 0:
                            print(f'Lidos {tot_files}')
                        if estimate:
                            continue
                        filename = join(dest_dir, arquivo.name)
                        with open(filename, 'r') as file:
                            texto = file.read()
                        if len(texto) > 0:
                            twitter_data = json.loads(texto)
                            tot_registros += processo.insere_docs(twitter_data)
                            processo.arquivos.append(filename)
                        else:
                            tot_erros += 1
                            continue

                        if len(processo.batch) >= processo.batch_size:
                            tot_fila += processo.commit()
                    except:
                        logger.error(f'Erro no arquivo {filename}', exc_info=True)
                        if exists(filename):
                            os.rename(filename, join(dest_dir, 'ruim', arquivo.name))
                        tot_erros += 1
                        if tot_erros > 10:
                            logger.error('Mais de 10 erros encontrados')
                            break

        if len(processo.batch) > 0:
            tot_fila += processo.commit()

        logger.info(f'Arquivos processados: {tot_files}')
        logger.info(f'Registros Lidos: {tot_registros}')
        logger.info(f'Registros Relevantes: {tot_fila}')
        logger.info(f'Arquivos com erro: {tot_erros}')
