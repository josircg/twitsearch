import json
import logging
import os
import sys
import time

from datetime import timedelta, datetime

from asgiref.sync import sync_to_async
from django.apps import AppConfig

from django.conf import settings
from django.utils import timezone

from twitsearch.local import get_api_client
from core import intdef

class CoreConfig(AppConfig):
    name = 'core'


def get_management_logger(name):
    logger = logging.getLogger(name)

    # Se o logger já tem handlers, não adiciona de novo (evita duplicados)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.propagate = False

        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

        # Garante que a pasta de logs existe (bom para o seu Debian)
        log_dir = os.path.join(settings.BASE_DIR,'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Handler de Arquivo
        fh = logging.FileHandler(f'{log_dir}/{name}.log')
        fh.setFormatter(formatter)

        # Handler de Console
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger


# Versão do log_message para rotinas assincronas
async def alog_message(instance, message, user=None):

    from django.contrib.auth import get_user_model
    from django.contrib.admin.models import LogEntry, CHANGE
    from django.contrib.contenttypes.models import ContentType

    if not user:
        user_model = get_user_model()
        user = await user_model.objects.aget(username='sys')

    content_type_id = await sync_to_async(
        lambda: ContentType.objects.get_for_model(instance).id
    )()

    await LogEntry.objects.acreate(
            user_id=user.pk,  # ID de um usuário admin/sistema dedicado
            content_type_id=content_type_id,
            object_id=instance.pk,
            object_repr=str(instance)[:200],
            action_flag=CHANGE,
            change_message=message,
        )


def save_result(data, processo,
                grava_termo=True, overwrite=True, opensearch=None):
    data['process'] = processo.id
    if grava_termo:
        data['termo'] = processo.termo.id
        data['projeto'] = processo.termo.projeto.id
    
    filename = f"{settings.BASE_DIR}/data/{data['id']}_{processo.termo.id}.json"
    if overwrite or not os.path.exists(filename):
        with open(filename, 'w') as arquivo:
            json.dump(data, arquivo)

    filename = f"{settings.BASE_DIR}/data/queue/{data['id']}_{processo.termo.id}.json"
    with open(filename, 'w') as arquivo:
        json.dump(data, arquivo)

    # if opensearch:
    #    today = datetime.now()
    #    index_name = f"twitter-{today.year}-{today.month}"
    #    save_object(opensearch, data, index_name)

    return True
    

def find_first_tweet(termo):
    client = get_api_client()
    start_time = termo.dtinicio
    dt_final = termo.dtfinal or (timezone.now() - timedelta(days=1))
    busca = termo.busca
    if termo.language:
        busca = f'{busca} lang:{termo.language}'
    minutes = 30
    tot_registros = 0
    prim_tweet = None
    while tot_registros == 0:
        end_time = start_time + timedelta(minutes=minutes)
        print(start_time, end_time)
        if end_time > dt_final:
            break
        tweets = client.search_all_tweets(query=busca, tweet_fields='created_at,id',
                                          start_time=start_time, end_time=end_time, max_results=10)
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
            time.sleep(10)
    return prim_tweet