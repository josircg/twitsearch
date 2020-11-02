import os
import re
import shlex

from django.apps import AppConfig

import subprocess

from twitsearch import settings

# Mon Nov 25 23:56:33 +0000 2019	25/11/2019 23:56:33
# def convert_date(dt):
#    return dt.strftime("%a %b %d %H:%M:%S %z %Y")


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

