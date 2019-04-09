# coding: utf-8
from django.utils.encoding import python_2_unicode_compatible
from django.db import models
from django.contrib.auth.models import User


class UserAdminConfig(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    url_name = models.CharField(max_length=100)  # identify the config
    url_full_path = models.TextField()

    def __str__(self):
        return u'%s' % self.url_name