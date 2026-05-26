# Exporta os dados da pasta cached para o Datalake no PostgreSQL
# A rotina de captura do vtrack vai passar a buscar os dados do Datalake e não mais do Opensearch
# Josir - 05/2026
#

import json
import os

from os.path import join, exists

import psycopg2 as psycopg

from django.conf import settings
from django.core.management.base import BaseCommand

from core.apps import get_management_logger

logger = get_management_logger("export_datalake")


def connect_postgresql(server: str):
    server = settings.PG_SERVERS.get(server)
    if not server:
        raise Exception('PG_SERVERS não encontrado')
    host = server['host']
    port = server.get('port',5432)
    database = server['database']
    username = server['username']
    password = server['password']
    pg = psycopg.connect(f"dbname={database} user={username} password={password} host={host} port={port}")
    return pg


class Processo:

    def __init__(self, pg_server, batch_size=500):
        self.pg_client = connect_postgresql(pg_server)
        self.counter_tweets = 0
        self.termos_processados = {}
        self.batch_size = batch_size
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
        Move o antigo para o histórico (mantendo o batch_id antigo) e insere o novo com o batch_id atual.
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
        self.pg_client.commit()
        self.batch = {}
        # Exclui os arquivos que foram processados
        for arquivo in self.arquivos:
            os.remove(arquivo)
        self.arquivos = []


class Command(BaseCommand):
    label = 'Importa Tweets'

    def add_arguments(self, parser):
        parser.add_argument('-t', '--tweet', type=str, help='Tweet específico', nargs='?')
        parser.add_argument('-d', '--verbose', help='Inclui detalhamento durante o processo',
                            action='store_true')

    def handle(self, *args, **options):

        tot_files = 0
        tot_erros = 0
        tot_registros = 0
        dest_dir = settings.BASE_DIR + '/data/cached'
        processo = Processo('pg_baoba', 500)
        for arquivo in os.scandir(dest_dir):
            if arquivo.name.endswith(".json"):
                try:
                    if tot_files > 20:
                        break
                    tot_files += 1
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
                        processo.commit()
                except:
                    logger.error(f'Erro no arquivo {filename}', exc_info=True)
                    if exists(filename):
                        os.rename(filename, join(dest_dir, 'ruim', arquivo.name))
                    tot_erros += 1
                    if tot_erros > 10:
                        logger.error('Mais de 10 erros encontrados')
                        break

        if len(processo.batch) > 0:
            processo.commit()

        logger.info(f'Arquivos processados: {tot_files}')
        logger.info(f'Registros: {tot_registros}')
        logger.info(f'Arquivos com erro: {tot_erros}')

