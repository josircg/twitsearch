# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from datetime import datetime, timedelta

from core.models import *

from twitsearch.settings import TIME_ZONE
from core.models import Termo

from core.apps import generate_tags_file
import boto3


class Command(BaseCommand):
    label = 'Generate csv tags file'

    def add_arguments(self, parser):
        parser.add_argument('--projeto', type=str, help='Projeto')

    def handle(self, *args, **options):
        boto3.setup_default_session(profile_name='admin-irdx')
        s3 = boto3.resource('s3')
        s3.meta.client.upload_file('/home/josir/bitbucket/twitsearch/excecoes.txt',
                                   'twitsearch-irdx', 'excecoes.txt')
        return
