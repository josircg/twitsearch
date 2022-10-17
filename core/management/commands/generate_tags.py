# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from datetime import datetime, timedelta

from core.models import *

from twitsearch.settings import TIME_ZONE
from core.models import Termo

from core.apps import generate_tags_file


class Command(BaseCommand):
    label = 'Generate csv tags file'

    def add_arguments(self, parser):
        parser.add_argument('--projeto', type=str, help='Projeto')

    def handle(self, *args, **options):
        id_projeto = options['projeto']
        tweets = Tweet.objects.filter(termo__projeto_id=id_projeto)
        generate_tags_file(tweets, id_projeto)
        return
