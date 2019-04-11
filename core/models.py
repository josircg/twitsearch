from django.db import models
from django.contrib.auth.models import User

import time
import pytz
from datetime import datetime


# Converte datas que venham no formato do Twitter
def convert_date(date_str) -> datetime:
    time_struct = time.strptime(date_str, '%a %b %d %H:%M:%S +0000 %Y')
    return datetime.fromtimestamp(time.mktime(time_struct)).replace(tzinfo=pytz.UTC)


class Projeto(models.Model):
    nome = models.CharField(max_length=20)
    objetivo = models.TextField('Objetivo')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)

    def __str__(self):
        return self.nome

    @property
    def tot_twits(self):
        soma = 0
        for termo in self.termo_set.all():
            soma += termo.tot_twits()
        return soma


STATUS_TERMO = (('A', 'Ativo'), ('P', 'Processando'),
                ('I', 'Interrompido'), ('C', 'Concluido'))


class Termo(models.Model):
    busca = models.CharField(max_length=200)
    projeto = models.ForeignKey(Projeto, on_delete=models.PROTECT)
    dtinicio = models.DateTimeField('Início da Busca', null=True, blank=True,
                                    help_text='Deixe em branco caso queira iniciar imediatamente')
    dtfinal = models.DateTimeField('Fim da Busca')
    status = models.CharField(max_length=1, choices=STATUS_TERMO, default='A')

    def __str__(self):
        return self.busca

    @property
    def tot_twits(self):
        return self.tweet_set.count() or 0
    # count.short_description = u'Total de Twits'

    class Meta:
        verbose_name = 'Termo de Busca'
        verbose_name_plural = 'Termos de Busca'


class Processamento(models.Model):
    termo = models.ForeignKey(Termo, on_delete=models.CASCADE)
    dt = models.DateTimeField()

    def __str__(self):
        return '%s (%s)' % (self.termo, self.dt)


class TweetUser(models.Model):
    twit_id = models.BigIntegerField(primary_key=True)
    username = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200, null=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateField()

    def __str__(self):
        return u'%s (%s)' % (self.username, self.location)

    @property
    def followers(self):
        return self.followershistory_set.latest('dt').followers

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários do Twitter'


class FollowersHistory(models.Model):
    user = models.ForeignKey(TweetUser, on_delete=models.CASCADE)
    followers = models.BigIntegerField()
    favourites = models.BigIntegerField()
    dt = models.DateField()

    def __str__(self):
        return u'%s em %s' % (self.user, self.dt)

    class Meta:
        ordering = ('dt', )
        verbose_name = 'Histórico de Seguidores'
        verbose_name_plural = 'Históricos de Seguidores'


class Tweet(models.Model):
    twit_id = models.CharField(max_length=21, primary_key=True)
    text = models.CharField(max_length=320)
    created_time = models.DateTimeField()
    retweets = models.IntegerField()
    favorites = models.IntegerField()
    user = models.ForeignKey(TweetUser, on_delete=models.CASCADE)
    termo = models.ForeignKey(Termo, on_delete=models.SET_NULL, null=True)
    retwit_id = models.CharField(max_length=21,null=True)

    def __str__(self):
        return self.twit_id


class TweetInput(models.Model):
    tweet = models.ForeignKey(Tweet, on_delete=models.CASCADE)
    processamento = models.ForeignKey(Processamento, on_delete=models.CASCADE)
    instante = models.DateTimeField(auto_now_add=True)
