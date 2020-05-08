import csv
import io
import os
import zipfile

from django.apps import AppConfig

import subprocess

from django.conf import settings
from django.http import HttpResponse
from twitsearch.settings import BASE_DIR


class CoreConfig(AppConfig):
    name = 'core'


def OSRun(command, stop=False):
    out = u''
    try:
        if type(command) != list:
            command = command.split(" ")
        print(repr(command))
        sp = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = sp.communicate()
        if stderr:
            out += u'ERROR: %s\n' % stderr.decode('utf-8')
        if stdout:
            out += u'%s\n' % stdout
    except OSError as err:
        out += 'Command:%s\n' % command
        out += "OS error: {0}".format(err)
        if stop:
            raise Exception(stderr)
    return out


# Mon Nov 25 23:56:33 +0000 2019	25/11/2019 23:56:33
def convert_date(dt):
    return dt.strftime("%a %b %d %H:%M:%S %z %Y")


def export_tags_action(description=u"Exportar para Tags"):
    def export_tags(modeladmin, request, queryset):
        generate_tags_file(filename='tags', queryset=queryset)
        with open(os.path.join(BASE_DIR, 'data', 'tags.zip'), 'rb') as f:
            file_data = f.read()
        response = HttpResponse(file_data, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename=tags_%s.zip' % modeladmin.opts.db_table
        return response

    export_tags.short_description = description
    return export_tags


def generate_tags_file(queryset, filename):
    path = os.path.join(BASE_DIR, 'data')
    csvfile = open(os.path.join(path, '%s.csv' % filename), 'w')
    writer = csv.writer(csvfile)
    writer.writerow(['id_str', 'from_user', 'text', 'created_at',
                     'time', 'geo_coordinates', 'user_lang', 'in_reply_to_user_id', 'in_reply_to_screen_name',
                     'from_user_id_str', 'in_reply_to_status_id_str', 'source', 'profile_image_url',
                     'user_followers_count', 'user_friends_count', 'user_location',
                     'status_url', 'entities_str'])
    num_lines = 0
    for obj in queryset:
        if obj.text[0:1] != 'RT':
            line = [obj.twit_id, obj.user.twit_id, obj.text, obj.created_time.strftime("%a %b %d %H:%M:%S %z %Y"),
                    obj.created_time.strftime("%d/%m/%Y %H:%M:%S"), '', obj.language, '', '',
                    '', '', '', '',
                    obj.user.followers, 0, obj.user.location,
                    '', '{"hashtags":[],"symbols":[],"user_mentions":[],"urls":[]}']
            writer.writerow(line)
            num_lines += 1
            for retweet in obj.retweet_set.filter(retweet_id__isnull=False):
                line = [retweet.retweet_id, retweet.user.twit_id, 'RT ' + obj.text,
                        obj.created_time.strftime("%a %b %d %H:%M:%S %z %Y"),
                        obj.created_time.strftime("%d/%m/%Y %H:%M:%S"), '', obj.language, '', '',
                        '', '', '', '',
                        obj.user.followers, 0, obj.user.location,
                        '', '{"hashtags":[],"symbols":[],"user_mentions":[],"urls":[]}']
                writer.writerow(line)
                num_lines += 1

    csvfile.close()
    # propositalmente estou enviando apenas o log
    filename_log = BASE_DIR + '/data/tags.log'
    logfile = open(filename_log, 'w')
    logfile.writelines(['Linhas exportadas:%d' % num_lines])
    logfile.close()

    path_zip = os.path.join(path, '%s.zip' % filename)
    with zipfile.ZipFile(path_zip, 'w') as zip:
        zip.write(os.path.join(path, '%s.csv' % filename), '%s.csv' %filename)

    #return path_zip


def export_extra_action(description=u"Exportar CSV com retweets"):

    def export_extra(modeladmin, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=full%s.csv' % modeladmin.opts.db_table

        writer = csv.writer(response)
        writer.writerow(['tweet_id', 'text', 'user', 'user_id', 'created_time',
                         'retweets', 'favorites', 'tweet_original'])
        for obj in queryset:
            line = [obj.twit_id, obj.text, obj.user, obj.user.twit_id,
                    obj.created_time.strftime("%a %b %d %H:%M:%S %z %Y"),
                    obj.retweets, obj.favorites, ]
            writer.writerow(line)
            for retweet in obj.retweet_set.filter(retweet_id__isnull=False):
                line = [retweet.retweet_id, 'RT '+retweet.tweet.text, retweet.user, retweet.user.twit_id,
                        obj.created_time.strftime("%a %b %d %H:%M:%S %z %Y"), 0, 0, retweet.tweet.twit_id]
                writer.writerow(line)
        return response
    export_extra.short_description = description
    return export_extra
