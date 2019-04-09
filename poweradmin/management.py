# -*- coding: utf-8
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django.db.models import signals
from django.conf import settings


def create_and_update_permissions(sender, app_config, **kwargs):
    app_name = app_config.name.split('.')[-1]

    for ct in ContentType.objects.filter(app_label=app_name):
        for action in ('add', 'change', 'delete', 'view', 'browser'):
            codename = u'%s_%s' % (action, ct.model)
            name = u'Can %s %s' % (action, ct.name)
            if not Permission.objects.filter(codename=codename).exists():
                Permission(codename=codename, name=name, content_type=ct).save()
            else:
                for permission in Permission.objects.filter(codename=codename):
                    if permission.name != name:
                        print("Updating Permission's name: '%s' -> '%s'" % (permission.name, name, ))
                        permission.name=name
                        permission.save()


signals.post_migrate.connect(create_and_update_permissions)