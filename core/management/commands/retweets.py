# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from core.models import *
from django.db.transaction import set_autocommit, commit


class Command(BaseCommand):
    label = 'Batch Update Retweet'

    def add_arguments(self, parser):
        parser.add_argument('-t', '--twit', type=str, help='Twitter File',)

    def handle(self, *args, **options):

        if options['twit']:
            dset = Tweet.objects.filter(twit_id=options['twit'], retwit_id__isnull=False)
        else:
            dset = Tweet.objects.filter(retwit_id__isnull=False)

        tot_files = 0
        set_autocommit(False)
        for tweet in dset:
            original = Tweet.objects.get(twit_id=tweet.retwit_id)
            Retweet.objects.get_or_create(tweet=original, user=tweet.user, created_time=tweet.created_time)
            tweet.delete()
            commit()
            tot_files += 1

        print('ReTweets processados: %d' % tot_files)
