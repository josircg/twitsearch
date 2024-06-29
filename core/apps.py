import datetime
import json
import os

from django.apps import AppConfig

from django.conf import settings
from django.utils import timezone

from twitsearch.local import get_api_client

class CoreConfig(AppConfig):
    name = 'core'


def save_result(data, processo_id, overwrite=True):
    data['process'] = processo_id
    filename = '%s/data/%s.json' % (settings.BASE_DIR,data['id'])
    if overwrite or not os.path.exists(filename):
        with open(filename, 'w') as arquivo:
            json.dump(data, arquivo)
            return True
    return False
    # print('%s saved' % filename)



def calcula_estimativa(termo, dt_inicial):
    client = get_api_client()
    agora = timezone.now() - datetime.timedelta(hours=1)
    start_time = dt_inicial.isoformat()
    end_time = min(termo.dtfinal, agora).isoformat()
    response = client.get_recent_tweets_count(termo.busca, granularity="day",
                                              start_time=start_time,
                                              end_time=end_time)
    total = 0
    for count in response.data:
        total +=  count['tweet_count']
    return total