import os
import zipfile
import boto3

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import *
from core import log_message


# A rotina remove todos os jsons de um determinado projeto
def remove_json(projeto):
    root_path = os.path.split(settings.MEDIA_ROOT)[:-1][0]
    root_path = os.path.join(root_path, 'data')
    tot_geral = 0
    for tweet in Tweet.objects.filter(termo__projeto_id=projeto.id). \
            select_related('twit_id').values_list('twit_id'):

        tweet_id = tweet[0]
        json_filename = os.path.join(root_path, 'cached', '%s_.json' % tweet_id)
        if os.path.exists(json_filename):
            os.remove(json_filename)
            tot_geral += 1
        else:
            json_filename = os.path.join(root_path, 'cached', '%s.json' % tweet_id)
            if os.path.exists(json_filename):
                os.remove(json_filename)
                tot_geral += 1

    if tot_geral > 0:
        print('Total de arquivos excluídos: %d' % tot_geral)
        log_message(projeto, 'JSON excluídos')
    return


class Command(BaseCommand):
    label = 'Remove os arquivos JSON de um projeto'

    def add_arguments(self, parser):
        parser.add_argument('--project', type=str, help='Projet ID')

    def handle(self, *args, **options):
        try:
            id_projeto = options['project']
            projeto = Projeto.objects.get(id=id_projeto)
        except Projeto.DoesNotExist:
            print('Projeto não encontrado')
            exit(1)

        remove_json(projeto)
