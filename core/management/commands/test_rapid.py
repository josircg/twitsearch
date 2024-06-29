# -*- coding: utf-8 -*-
import json
from django.core.management.base import BaseCommand
from django.db.transaction import set_autocommit, commit
from core.models import Termo

from twitsearch.local import get_api
import tweepy
import requests
import ast
from datetime import datetime


class Command(BaseCommand):
    label = 'Teste Rapid API'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='JSON File')

    # https://rapidapi.com/Glavier/api/twitter135
    # "vacinação infantil" since:2023-01-01
    def handle(self, *args, **options):
        url = "https://twitter135.p.rapidapi.com/Search/"

        now = datetime.now()

        if options['file']:
            with open(options['file'],'r') as arquivo:
                data = arquivo.read()
            json_data = ast.literal_eval(data)
        else:
            querystring = {"q": "vacinação infantil", "count": "100"}

            headers = {
                "X-RapidAPI-Key": "3d05fb8fadmsh6be1466bf438d0ap17ec13jsn5bdc34be8037",
                "X-RapidAPI-Host": "twitter135.p.rapidapi.com"
            }

            response = requests.get(url, headers=headers, params=querystring)

            if response.status_code == 200:
                json_data = response.json()
            else:
                if response.content:
                    print(response.content.json())

        if json_data:
            for tweet in json_data["globalObjects"]["tweets"].values():
                filename = 'data/%s.json' % tweet['id']
                arquivo = open(filename, 'w')
                json.dump(tweet, arquivo)
                arquivo.close()

            str_now = f'{now.year}{now.month}{now.day}-{now.hour}{now.minute}{now.second}'
            arquivo = open(f'data/{str_now}-user.json', 'w')
            json.dump(json_data["globalObjects"]["tweets"], arquivo)
            arquivo.close()


