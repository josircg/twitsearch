import time
import pytz
from datetime import datetime
from collections import Counter

from django.db import models, connection
from django.db.models import Sum
from django.contrib.auth.models import User

from twitsearch.settings import BASE_DIR


# Converte datas que venham no formato do Twitter
def convert_date(date_str) -> datetime:
    time_struct = time.strptime(date_str, '%a %b %d %H:%M:%S +0000 %Y')
    return datetime.fromtimestamp(time.mktime(time_struct)).replace(tzinfo=pytz.UTC)


def stopwords() -> list:
    excecoes = []
    for line in open(BASE_DIR+'/excecoes.txt').readlines():
        for words in line.split(','):
            excecoes.append(words.strip().lower())
    return excecoes


def clean_pontuation(s) -> str:
    result = ''
    for letter in s:
        if letter not in ['.', ',', '?', '!', '"', "'"]:
            result += letter
    return result


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
            soma += termo.tweet_set.count()
        return '{:,}'.format(soma).replace(',','.')

    @property
    def tot_retwits(self):
        soma = 0
        for termo in self.termo_set.all():
            soma += termo.tot_retwits
        return '{:,}'.format(soma).replace(',','.')

    def top_tweets(self):
        top_tweets = Counter()
        return None

    @property
    def unique_users(self):
        with connection.cursor() as cursor:
            cursor.execute("select count(distinct user_id) from" +
                           "(select distinct c.user_id from core_tweet c, core_termo e" +
                           " where e.projeto_id = %s and e.id = c.termo_id" +
                           " union " +
                           " select distinct r.user_id from core_termo e, core_tweet as t, core_retweet as r" +
                           " where e.projeto_id = %s and e.id = t.termo_id and t.twit_id = r.tweet_id) as uniao",
                           [self.id, self.id])
            soma = cursor.fetchone()[0]
        return '{:,}'.format(soma).replace(',','.')

    @property
    def status(self):
        _status = 'C'
        for termo in self.termo_set.all():
            if termo.status == 'P':
                _status = 'P'
                termo.get_status_display()
            elif _status not in ('P', 'I'):
                _status = termo.status
        return dict(STATUS_TERMO).get(_status)

    def most_common(self):
        result = Counter()
        excecoes = stopwords()
        for termo in self.termo_set.all():
            # adiciona os termos de busca na exceção para que eles não distorçam o grupamento
            for busca in termo.busca.split():
                excecoes.append(clean_pontuation(busca))

            for tweet in termo.tweet_set.all():
                palavras = tweet.text.lower().split()
                for palavra in palavras:
                    if not palavra.startswith('http') and not palavra.startswith('@'):
                        palavra_limpa = clean_pontuation(palavra)
                        if palavra_limpa not in excecoes:
                            if len(palavra_limpa) > 3:
                                result[palavra_limpa] += 1
        return result.most_common(20)


STATUS_TERMO = (('A', 'Ativo'), ('P', 'Processando'),
                ('I', 'Interrompido'), ('C', 'Concluido'))


class Termo(models.Model):
    busca = models.CharField(max_length=200)
    projeto = models.ForeignKey(Projeto, on_delete=models.PROTECT)
    dtinicio = models.DateTimeField('Início da Busca', null=True, blank=True,
                                    help_text='Deixe em branco caso queira iniciar imediatamente')
    dtfinal = models.DateTimeField('Fim da Busca')
    status = models.CharField(max_length=1, choices=STATUS_TERMO, default='A')
    ult_processamento = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.busca

    @property
    def tot_twits(self):
        return self.tweet_set.count() or 0

    @property
    def tot_retwits(self):
        total = Tweet.objects.filter(termo=self).aggregate(Sum('retweets'))['retweets__sum']
        return total or 0

    @property
    def unique_users(self):
        with connection.cursor() as cursor:
            cursor.execute("select count(distinct user_id) from" +
                           "(select distinct c.user_id from core_tweet c where c.termo_id = %s" +
                           " union " +
                           " select distinct r.user_id from core_tweet as t, core_retweet as r" +
                           " where t.twit_id = r.tweet_id and t.termo_id = %s) as uniao",
                           [self.id, self.id])
            total = cursor.fetchone()[0]
        return total or 0

    def last_tweet(self):
        last = self.tweet_set.last()
        if last:
            return last.twit_id
        else:
            return None

    class Meta:
        verbose_name = 'Termo de Busca'
        verbose_name_plural = 'Termos de Busca'


PROC_IMPORTACAO = 'I'
PROC_IMPORTUSER = 'U'
PROC_TAGS = 'T'
PROC_NETWORK = 'N'
TIPO_PROCESSAMENTO = ((PROC_IMPORTACAO,'Importação'),
                      (PROC_IMPORTUSER,'Importação User'),
                      (PROC_TAGS,'Exportação Tags'),
                      (PROC_NETWORK,'Montagem Rede'))


class Processamento(models.Model):
    termo = models.ForeignKey(Termo, on_delete=models.CASCADE, null=True)
    dt = models.DateTimeField()
    twit_id = models.CharField('Último Tweet baixado', max_length=21, blank=True, null=True)
    tipo = models.CharField(max_length=1, choices=TIPO_PROCESSAMENTO, default=PROC_IMPORTACAO)

    def __str__(self):
        return '%s (%s)' % (self.termo, self.dt)

    @property
    def tot_twits(self):
        return self.tweetinput_set.count() or 0


class Credencial(models.Model):
    username = models.CharField(max_length=100)
    key = models.CharField(max_length=30)
    secret = models.CharField(max_length=30)
    token = models.CharField(max_length=30)
    token_secret = models.CharField(max_length=30)
    last_conn = models.DateTimeField(null=True)


class LockProcessamento(models.Model):
    locked = models.BooleanField(default=False)
    dt_inicio = models.DateTimeField(auto_now=True)


class TweetUser(models.Model):
    twit_id = models.BigIntegerField(primary_key=True)
    username = models.CharField(max_length=100, null=True)
    name = models.CharField(max_length=200, null=True)
    location = models.CharField(max_length=200, null=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateField()
    followers = models.BigIntegerField(default=0)

    def __str__(self):
        return u'%s (%s)' % (self.username, self.location[:20])

    class Meta:
        verbose_name = 'Usuário do Twitter'
        verbose_name_plural = 'Usuários do Twitter'
        ordering = ['twit_id', ]


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
    retwit_id = models.CharField(max_length=21, null=True)
    language = models.CharField(max_length=5, null=True)

    def __str__(self):
        return self.twit_id


class Retweet(models.Model):
    tweet = models.ForeignKey(Tweet)  # Tweet original que gerou o retwet
    user = models.ForeignKey(TweetUser)
    created_time = models.DateTimeField(null=True)
    retweet_id = models.CharField(max_length=21, null=True)  # id do retweet

    def __str__(self):
        return self.user.username

    # Intervalo de tempo entre a postagem original e o retweet (em minutos)
    def tweet_dif(self):
        dif = self.created_time - self.tweet.created_time
        if dif.days > 1:
            return '%d dias' % dif.days
        else:
            if dif.total_seconds() < 60:
                return 'primeiro minuto'
            else:
                duration_in_s = dif.total_seconds()
                return '%d minutos' % divmod(duration_in_s, 60)[0]


class TweetInput(models.Model):
    tweet = models.ForeignKey(Tweet, on_delete=models.CASCADE)
    processamento = models.ForeignKey(Processamento, on_delete=models.CASCADE)
    instante = models.DateTimeField(auto_now_add=True)
