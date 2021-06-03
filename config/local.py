# -*- coding: utf-8 -*-
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
        'PASSWORD': 'xxxx',
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}

SECRET_KEY = 'vvo&l_gb%m17nxyr^m_hkc44^k$^5$d&08@47cpej-+d^!pl'


def get_api():
    auth = tweepy.OAuthHandler(
                consumer_key='XXXXX',
                consumer_secret='XXXXX')
    auth.set_access_token(
            'XXX',
            'XXX')
    return tweepy.API(auth, wait_on_rate_limit=True)
