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


def get_api():
    auth = tweepy.OAuthHandler(
                consumer_key='xxxx',
                consumer_secret='xxxx')
    auth.set_access_token(
            'xxxx',
            'xxxx')
    return tweepy.API(auth, wait_on_rate_limit=True)