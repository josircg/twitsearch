"""
twitsearch/local.py do ambiente Docker de teste do deploy (montado por volume no compose).
Conecta no MySQL do docker compose (serviço mysql) e só sobrescreve o necessário para simular produção.
DEBUG=False para que o deploy realmente reinicie o serviço no supervisor.
"""
from twitsearch.settings import *  # noqa: F401,F403

DEBUG = False
DEBUG_TOOLBAR = False
SECRET_KEY = 'docker-test-only'
ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = ['http://localhost:8080', 'http://127.0.0.1:8080']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'twitprod',
        'USER': 'twitsearch',
        'PASSWORD': 'teste123',
        'HOST': 'mysql',
        'PORT': '3306',
        'OPTIONS': {'init_command': "SET sql_mode='STRICT_TRANS_TABLES'", 'charset': 'utf8mb4'},
    }
}
BEARED_TOKEN = ''
AUTH_KEYS = {}


def get_api_client():
    return None
