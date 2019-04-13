from django.apps import AppConfig

import subprocess


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