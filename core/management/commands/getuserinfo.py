import json
import requests
import pytz
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from core import convert_date
from core.models import TweetUser, FollowersHistory


class Command(BaseCommand):
    label = 'Get User data'
    agora = datetime.now(pytz.timezone(settings.TIME_ZONE))
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
            user_data = response.json().get('data',[])
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

            json_data = response.json()
            user_data = json_data.get('errors',[])
            for user_record in user_data:
                user = TweetUser.objects.get(twit_id=user_record['value'])
                user.username = '<Deleted>'
                user.save()
                user_saved.append(user_record['value'])

            missed = set(user_list) - set(user_saved)
            if len(missed) > 0:
                print(missed)

    def handle(self, *args, **options):

        self.header = {'Authorization': 'Bearer %s' % settings.BEARED_TOKEN}
        limite_busca = 100
        user_list = []
        total = TweetUser.objects.filter(username__isnull=True).count()
        print(f'Usuários sem info: {total} - Buscando apenas {limite_busca}')
        for empty_user in TweetUser.objects.filter(username__isnull=True).only('twit_id'):

            user_list.append(str(empty_user.twit_id))
            self.tot_registros += 1
            if self.tot_registros % 100 == 0:
                self.update_users(user_list)
                print(f'{self.tot_updates}')
                user_list = []

                if self.tot_registros > limite_busca:
                    break

        if len(user_list) > 0:
            self.update_users(user_list)
        print(f'Total de usuários lidos: {self.tot_registros}')
        print(f'Total de usuários atualizados: {self.tot_updates}')



