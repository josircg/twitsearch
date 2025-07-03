from twitsearch.settings import *

import tweepy

DEBUG = True

ADMINS = (
    (u'Admin', 'admin@admin.com'),
)
MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'twitprod',
        'USER': 'twitsearch',
        'PASSWORD': 'xxxxx',
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}

SECRET_KEY = 'xxxxx'
AWS_PROFILE = 'admin-irdx'
AWS_BUCKET = 'twitsearch-irdx'

# Permissões para acessar a API
AUTH_KEYS = {
    '123': True,
    '234': True
}

