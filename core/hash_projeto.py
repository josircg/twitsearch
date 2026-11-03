import hashlib
import hmac

from django.conf import settings


def hash_projeto(projeto_id, ds):
    msg = f'projeto:{projeto_id}:{ds}'.encode()
    return hmac.new(settings.PROJETO_HASH_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]


def token_projeto(projeto_id, ds):
    return f'{projeto_id}-{hash_projeto(projeto_id, ds)}'
