import os
import re
import shlex
import subprocess
import time
import pytz
from datetime import datetime

from twitsearch import settings

# Mon Nov 25 23:56:33 +0000 2019	25/11/2019 23:56:33
# def convert_date(dt):
#    return dt.strftime("%a %b %d %H:%M:%S %z %Y")

from twitsearch.settings import BASE_DIR


def intdef(s, default: int = 0) -> int:
    try:
        return int(s)
    except ValueError:
        return default
    except TypeError:
        return default


def clean_pontuation(s) -> str:
    result = ''
    for letter in s:
        if letter not in ['.', ',', ':', '?', '!', '"', "'", "”", '“', ')', '(','-']:
            result += letter
    return result


def stopwords() -> list:
    excecoes = []
    for line in open(BASE_DIR+'/excecoes.txt').readlines():
        for words in line.split(','):
            excecoes.append(words.strip().lower())
    return excecoes


def find_urls(text):
    urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',text)
    return urls


# Converte datas que venham no formato do Twitter
def convert_date(date_str) -> datetime:
    if 'Z' in date_str:
        '2022-03-05T13:17:21.000Z'
        time_struct = time.strptime(date_str, '%Y-%m-%dT%H:%M:%S.000Z')
    else:
        time_struct = time.strptime(date_str, '%a %b %d %H:%M:%S +0000 %Y')
    return datetime.fromtimestamp(time.mktime(time_struct)).replace(tzinfo=pytz.UTC)


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
            raise Exception(out)
    return out


def check_dir(path):
    if not os.path.exists(path):
        if not os.path.exists(settings.MEDIA_ROOT):
            os.mkdir(settings.MEDIA_ROOT)
        os.mkdir(path)


def tokenize(self, line: str):
    """Lex a string into a list of tokens.

    Comments are removed, and shortcuts and aliases are expanded.

    Raises ValueError if there are unclosed quotation marks.
    """

    # strip C-style comments
    # shlex will handle the python/shell style comments for us
    line = re.sub(self.comment_pattern, self._comment_replacer, line)

    # expand shortcuts and aliases
    line = self._expand(line)

    # split on whitespace
    lexer = shlex.shlex(line, posix=False)
    lexer.whitespace_split = True

    # custom lexing
    tokens = self._split_on_punctuation(list(lexer))
    return tokens


def log_message(instance, message, user=None):

    from django.contrib.auth import get_user_model
    from django.contrib.admin.models import LogEntry, CHANGE
    from django.contrib.contenttypes.models import ContentType

    if not user:
        user_model = get_user_model()
        user = user_model.objects.get_or_create(username='sys')[0]
    LogEntry.objects.log_action(
        user_id=user.pk,
        content_type_id=ContentType.objects.get_for_model(instance).pk,
        object_id=instance.pk,
        object_repr=u'%s' % instance,
        action_flag=CHANGE,
        change_message=message
    )