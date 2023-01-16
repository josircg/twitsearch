# -*- coding: utf-8 -*-
import json
import requests
import pytz

from datetime import datetime
from django.core.management.base import BaseCommand
from twitsearch.settings import TIME_ZONE
from core.models import convert_date, TweetUser, FollowersHistory

from searchtweets import load_credentials


class Command(BaseCommand):
    label = 'Get User data'
    agora = datetime.now(pytz.timezone(TIME_ZONE))
    header = None
    tot_registros = 0
    tot_updates = 0

    def update_users(self, user_list):
        response = requests.get(
            'https://api.twitter.com/2/users?ids=%s&user.fields=id,created_at,location,name,public_metrics,username,verified' %
            ','.join(user_list),
            headers=self.header)

        # alterar o TweetUser com os dados obtidos
        if response.status_code == 200:
            user_saved = []
            user_data = response.json()['data']
            for user_record in user_data:
                user = TweetUser.objects.get(twit_id=user_record['id'])
                user.name = user_record['name']
                user.username = user_record['username']
                user.verified = user_record['verified']
                if 'location' in user_record:
                    user.location = user_record['location']
                user.created_at = convert_date(user_record['created_at']).date()
                user.save()
                user_saved.append(user_record['id'])
                self.tot_updates += 1

                try:
                    FollowersHistory.objects.get(user=user)
                except FollowersHistory.DoesNotExist:
                    follow = FollowersHistory(user=user, dt=self.agora,
                                              followers=user_record['public_metrics']['followers_count'],
                                              favourites=user_record['public_metrics']['following_count'])
                    follow.save()

                follow = FollowersHistory.objects.filter(user=user).latest('dt')
                if user.followers != follow.followers:
                    user.followers = follow.followers
                    user.save()

                missed = set(user_list) - set(user_saved)
                print(missed)

    def handle(self, *args, **options):
        auth = load_credentials(filename="twitsearch/credentials.yaml",
                                yaml_key="oldimar",
                                env_overwrite=False)

        self.header = {'Authorization': 'Bearer %s' % auth['bearer_token']}

        user_list = []
        total = TweetUser.objects.filter(username__isnull=True).count()
        print(f'Usuários sem info: {total} - Buscando apenas 2000')
        for empty_user in TweetUser.objects.filter(username__isnull=True).only('twit_id'):

            user_list.append(str(empty_user.twit_id))
            self.tot_registros += 1
            if self.tot_registros % 100 == 0:
                self.update_users(user_list)
                print(f'{self.tot_updates}')
                user_list = []

                if self.tot_registros % 2000 == 0:
                    break

        if len(user_list) > 0:
            self.update_users(user_list)
        print(f'Total de usuários lidos: {self.tot_registros}')
        print(f'Total de usuários atualizados: {self.tot_updates}')



