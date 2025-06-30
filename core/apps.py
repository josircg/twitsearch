import datetime
import json
import os

from django.apps import AppConfig

from django.conf import settings
from django.utils import timezone

from twitsearch.local import get_api_client
from .opensearch import connect_opensearch, create_if_not_exists_index, save_object
class CoreConfig(AppConfig):
    name = 'core'


def save_result(data, processo, overwrite=True, opensearch=None):
    data['process'] = processo.id
    data['termo'] = processo.termo.id
    data['projeto'] = processo.termo.projeto.id
    
    filename = '%s/data/%s.json' % (settings.BASE_DIR,data['id'])
    if overwrite or not os.path.exists(filename):
        with open(filename, 'w') as arquivo:
            json.dump(data, arquivo)

    if opensearch:
        today = datetime.datetime.now()
        index_name = f"twitter-{today.year}-{today.month}"
        save_object(opensearch, data, index_name)

    return True
    


def calcula_estimativa(termo, dt_inicial):
    client = get_api_client()
    agora = timezone.now() - datetime.timedelta(hours=2)
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