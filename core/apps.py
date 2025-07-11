import json
import os
import time
from datetime import timedelta, datetime

from django.apps import AppConfig
from django.utils import timezone

from django.conf import settings
from django.utils import timezone

from twitsearch.local import get_api_client
from .opensearch import save_object
from core import intdef

class CoreConfig(AppConfig):
    name = 'core'


def save_result(data, processo, overwrite=True, opensearch=None):
    data['process'] = processo.id
    data['termo'] = processo.termo.id
    data['projeto'] = processo.termo.projeto.id
    
    filename = f"{settings.BASE_DIR}/data/{data['id']}_{processo.termo.id}.json"
    if overwrite or not os.path.exists(filename):
        with open(filename, 'w') as arquivo:
            json.dump(data, arquivo)

    if opensearch:
        today = datetime.now()
        index_name = f"twitter-{today.year}-{today.month}"
        save_object(opensearch, data, index_name)

    return True
    

def find_first_tweet(termo):
    client = get_api_client()
    start_time = termo.dtinicio
    end_time = termo.dtinicio
    dt_final = termo.dtfinal or (timezone.now() - timedelta(days=1))
    busca = termo.busca
    if termo.language:
        busca = f'{busca} lang:{termo.language}'
    minutes = 10
    tot_registros = 0
    prim_tweet = None
    while tot_registros == 0:
        end_time = start_time + timedelta(minutes=minutes)
        if end_time > dt_final:
            break
        tweets = client.search_all_tweets(query=busca, tweet_fields='created_at,id',
                                          start_time=start_time, end_time=end_time, max_results=50)
        if tweets.source.get('meta'):
            if tweets.source['meta'].get('result_count', 0) > 0:
                for tweet in tweets.source['data']:
                    current_id = intdef(tweet['id'], 0)
                    if prim_tweet:
                        prim_tweet = min(current_id, prim_tweet)
                    else:
                        prim_tweet = current_id
                    tot_registros += 1

        if tot_registros == 0:
            minutes = minutes * 60
            start_time = end_time
            time.sleep(1)
    return prim_tweet


def calcula_estimativa(termo, dt_inicial):
    client = get_api_client()
    agora = timezone.now() - timedelta(hours=2)
    start_time = dt_inicial.isoformat()
    total = 0
    if termo.dtfinal:
        end_time = min(termo.dtfinal, agora).isoformat()
    else:
        end_time = agora.isoformat()
    # se a última estimativa for maior que duas horas para traz, não trazer nada
    if start_time < end_time:
        response = client.get_recent_tweets_count(termo.busca, granularity="day",
                                                  start_time=start_time,
                                                  end_time=end_time)
        for count in response.data:
            total +=  count['tweet_count']
    return total