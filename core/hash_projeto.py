import hashlib
import hmac
import re

from django.conf import settings

# nome de índice aceito no link "Resultado"; o Gestão valida o parâmetro idx com a mesma expressão
REGEX_INDICE = re.compile(r'[a-z][a-z0-9-]{0,19}')


def indice_valido(indice):
    return bool(indice) and REGEX_INDICE.fullmatch(indice) is not None


def hash_projeto(projeto_id, ds, indice=''):
    # sem índice a mensagem é a mesma de antes, então links já enviados continuam válidos
    msg = f'projeto:{projeto_id}:{ds}:{indice}' if indice else f'projeto:{projeto_id}:{ds}'
    return hmac.new(settings.PROJETO_HASH_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]


def token_projeto(projeto_id, ds, indice=''):
    return f'{projeto_id}-{hash_projeto(projeto_id, ds, indice)}'
