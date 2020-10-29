# -*- coding: utf-8 -*-
import json
from django.core.management.base import BaseCommand
from django.db.transaction import set_autocommit, commit
from core.models import Termo

from twitsearch.local import get_api
import tweepy


class SimpleListener(tweepy.StreamListener):

    def __init__(self):
        super(SimpleListener, self).__init__()
        self.checkpoint = 50
        self.processo = None
        self.dtfinal = None

    def on_data(self, status):
        # code to run each time you receive some data (direct message, delete, profile update, status,...)
        data = json.loads(status)
        if 'disconnect' in data:
            if self.on_disconnect(data['disconnect']) is False:
                return False
        elif 'warning' in data:
            if self.on_warning(data['warning']) is False:
                print(data['warning'])
                return False

        return self.checkpoint > 0

    def on_error(self, status_code):
        # code to run each time an error is received
        if status_code == 420:
            return False
        else:
            return True

class Command(BaseCommand):
    label = 'Teste Concorrência'

    def handle(self, *args, **options):
        api = get_api()
        listener = SimpleListener()
        tweepy_stream = tweepy.Stream(auth=api.auth, listener=listener)
        tweepy_stream.filter(track=['racismo'], is_async=True)

    def handle_teste(self, *args, **options):
        Termo.objects.filter(id=1).update(status='P')
        status = 'A'
        while status != 'C':
            status = Termo.objects.get(id=1).status
        print('Concluído!')

