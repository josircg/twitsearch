# -*- coding: utf-8 -*-
import json
import datetime
import requests
import pytz

from django.core.management.base import BaseCommand
from twitsearch.settings import TIME_ZONE
from core.models import convert_date, TweetUser, FollowersHistory

from searchtweets import load_credentials


def save_result(data, processo):
    data['process'] = processo
    filename = 'data/%s_.json' % data['id']
    arquivo = open(filename, 'w')
    json.dump(data, arquivo)
    arquivo.close()
    print('%s saved' % filename)


class Command(BaseCommand):
    label = 'Teste API v2 - User data'

    def handle(self, *args, **options):
        auth = load_credentials(filename="twitsearch/credentials.yaml",
                                yaml_key="oldimar",
                                env_overwrite=False)

        header = {'Authorization': 'Bearer %s' % auth['bearer_token']}

        tot_registros = 0
        tot_updates = 0
        agora = datetime.now(pytz.timezone(TIME_ZONE))
        user_list = []
        for empty_user in TweetUser.objects.filter(username__isnull=True).only('twit_id'):

            user_list.append(str(empty_user.twit_id))
            tot_registros += 1
            if tot_registros % 100 == 0:

                response = requests.get(
                    'https://api.twitter.com/2/users?ids=%s&user.fields=id,created_at,location,name,public_metrics,username,verified' %
                    ','.join(user_list),
                    headers=header)

                # alterar o TweetUser com os dados obtidos
                if response.status_code == 200:
                    user_data = response.json()['data']
                    for user in user_data:
                        num_updates = \
                            TweetUser.objects.filter(twit_id=user['id']).\
                            update(location=user['location'], name=user['name'], username=user['username'],
                                   verified=user['verified'], created_at=convert_date(user['created_at']).date())
                        tot_updates += num_updates

                        try:
                            FollowersHistory.objects.get(user=user)
                        except FollowersHistory.DoesNotExist:
                            follow = FollowersHistory(user=user, dt=agora,
                                                      followers=user['public_metrics']['followers_count'],
                                                      favourites=user['public_metrics']['favourites_count'])
                            follow.save()

                        follow = FollowersHistory.objects.filter(user=user).latest('dt')
                        if user.followers != follow.followers:
                            user.followers = follow.followers
                            user.save()
                user_list = []

                if tot_registros % 2000:
                    break

        print(f'Total de usuários lidos: {tot_registros}')
        print(f'Total de usuários atualizados: {tot_updates}')



