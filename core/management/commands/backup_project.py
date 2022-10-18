import os
import zipfile
import boto3

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import *


class Command(BaseCommand):
    label = 'Backup dos arquivos json do projeto para o S3'

    def add_arguments(self, parser):
        parser.add_argument('--project', type=str, help='Projet ID')

    def handle(self, *args, **options):
        try:
            id_projeto = options['project']
            projeto = Projeto.objects.get(id=id_projeto)
        except Projeto.DoesNotExist:
            print('Projeto não encontrado')
            exit(1)

        try:
            bucket = settings.AWS_PROFILE + settings.AWS_BUCKET
        except:
            print('AWS Profile or Bucket not defined')
            exit(1)

        root_path = os.path.split(settings.MEDIA_ROOT)[:-1][0]
        root_path = os.path.join(root_path, 'data')
        tot_zips = 1
        tot_geral = 0
        tot_files = 0
        for tweet in Tweet.objects.filter(termo__projeto_id=id_projeto). \
                select_related('twit_id').values_list('twit_id'):

            if tot_files == 0:
                path_zip = os.path.join(root_path, 'projeto-%s-%d.zip' % (id_projeto, tot_zips))
                zipf = zipfile.ZipFile(path_zip, 'w', compression=zipfile.ZIP_DEFLATED)

            tweet_id = tweet[0]
            json_filename = os.path.join(root_path, 'cached', '%s.json' % tweet_id)
            if os.path.exists(json_filename):
                zipf.write(os.path.join(json_filename), '%s.json' % tweet_id)
                tot_files += 1
            else:
                json_filename = os.path.join(root_path, 'cached', '%s_.json' % tweet_id)
                if os.path.exists(json_filename):
                    zipf.write(os.path.join(json_filename), '%s.json' % tweet_id)
                    tot_files += 1

            if tot_files == 100000:
                tot_geral += tot_files
                tot_files = 0
                tot_zips += 1
                zipf.close()

        if tot_files != 0:
            tot_geral += tot_files
            zipf.close()

        if tot_geral > 0:
            print('Total de arquivos importados: %d' % tot_geral)
            boto3.setup_default_session(profile_name=settings.AWS_PROFILE)
            s3 = boto3.resource('s3')
            for file_number in range(1, tot_zips+1):
                zip_filename = 'projeto-%s-%d.zip' % (id_projeto, file_number)
                path_zip = os.path.join(root_path, zip_filename)
                s3.meta.client.upload_file(path_zip, settings.AWS_BUCKET, '%s/%s' % (projeto.nome, zip_filename))
                print('Arquivo copiado com sucesso %s' % zip_filename)
        return
