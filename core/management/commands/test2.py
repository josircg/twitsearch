# -*- coding: utf-8 -*-
import json
from django.core.management.base import BaseCommand
from core.models import convert_date

from searchtweets import ResultStream, gen_request_parameters, load_credentials, collect_results


def save_result(data, processo):
    data['process'] = processo
    filename = 'data/%s_.json' % data['id']
    arquivo = open(filename, 'w')
    json.dump(data, arquivo)
    arquivo.close()
    print('%s saved' % filename)


class Command(BaseCommand):
    label = 'Teste API v2'

    def handle(self, *args, **options):
        auth = load_credentials(filename="twitsearch/credentials.yaml",
                                yaml_key="oldimar",
                                env_overwrite=False)
        query = gen_request_parameters("from:CarlosBolsonaro", None,
                                       tweet_fields='id,text,public_metrics,author_id,conversation_id,created_at,'
                                                    'lang,in_reply_to_user_id,possibly_sensitive,'
                                                    'referenced_tweets',
                                       expansions='author_id,referenced_tweets.id,referenced_tweets.id.author_id',
                                       results_per_call=100, start_time='2018-10-01 00:00')
        tweets = ResultStream(request_parameters=query,
                              max_tweets=100, **auth)
        tot_registros = 0
        for dataset in tweets.stream():
            # Monta a matriz de usuários
            users = {}
            for user in dataset['includes']['users']:
                users[user['id']] = {'id': user['id'], 'screen_name': user['username'], 'name': user['name']}

            # Converte o tweet para o formato da API v1
            for tweet in dataset['data']:
                dt = convert_date(tweet['created_at']).date()
                tweet['retweet_count'] = tweet['public_metrics']['retweet_count']
                tweet['reply_count'] = tweet['public_metrics']['reply_count']
                tweet['favorite_count'] = tweet['public_metrics']['like_count']
                del tweet['public_metrics']
                if tweet['author_id'] in users:
                    tweet['user'] = users[tweet['author_id']]
                else:
                    tweet['user'] = {'id': tweet['author_id']}
                for parent in tweet.get('referenced_tweets', []):
                    if 'public_metrics' in parent:
                        parent['retweet_count'] = parent['public_metrics']['retweet_count']
                        parent['reply_count'] = parent['public_metrics']['reply_count']
                        parent['favorite_count'] = parent['public_metrics']['like_count']
                        del parent['public_metrics']

                    if 'author' in parent:
                        parent['user'] = parent['author']
                        del parent['author']
                    else:
                        if 'author_id' in parent:
                            if parent['author_id'] in users:
                                parent['user'] = users[parent['author_id']]
                            else:
                                parent['user'] = {'id': parent['author_id']}
                        else:
                            if 'in_reply_to_user' in tweet:
                                parent['user'] = tweet['in_reply_to_user']

                    if parent['type'] in ('replied_to', 'quoted'):
                        tweet['quoted_status'] = parent
                    else:
                        tweet['retweeted_status'] = parent

                save_result(tweet, 0)
                tot_registros += 1

        print(f'Total de tweets lidos: {tot_registros}')



