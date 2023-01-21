from collections import Counter

from django.db import models, connection
from django.db.models import Sum
from django.contrib.auth.models import User, Group
from django.utils.safestring import mark_safe

from twitsearch.settings import BASE_DIR

PROC_IMPORTACAO = 'I'   # Importação via busca regular
PROC_PREMIUM = 'A'      # Importação Premium
PROC_HISTORICO = 'H'    # Importação via busca histórica (GetOldTweets)
PROC_IMPORTUSER = 'U'   # Busca na rede tweets de um determinado usuário
PROC_RETWEET = 'R'      # Busca na rede retweets de um determinado tweet
PROC_BUSCAGLOBAL = 'G'  # Busca na base de dados, tweets que atendam a um critério
PROC_FILTROPROJ = 'P'   # Filtro dentro do projeto
PROC_MATCH = 'M'        # Faz o match de tweets orfãos de projeto
PROC_TAGS = 'T'         # Geração de arquivo CSV com as TAGs
PROC_NETWORK = 'N'      # Geração de Grafo
PROC_BACKUP = 'B'       # Backup JSON
PROC_JSON_IMPORT = 'J'  # Importação dos JSONs pendentes
PROC_FECHAMENTO = 'F'   # Fechamento do Projeto e cálculo das estatísticas

TIPO_BUSCA = (
    (PROC_IMPORTACAO, 'Importação Regular'),
    (PROC_PREMIUM,    'Importação Premium'),
    (PROC_IMPORTUSER, 'Importação Usuário'),
    (PROC_BUSCAGLOBAL,'Busca Global'),
    (PROC_FILTROPROJ, 'Busca no Projeto'),
)

TIPO_PROCESSAMENTO = (
    (PROC_IMPORTACAO,   'Importação'),
    (PROC_PREMIUM,      'Importação Premium'),
    (PROC_IMPORTUSER,   'Importação User'),
    (PROC_BUSCAGLOBAL,  'Busca Global'),
    (PROC_HISTORICO,    'Busca Histórica'),
    (PROC_FILTROPROJ,   'Busca no Projeto'),
    (PROC_BACKUP,       'Backup JSON'),
    (PROC_MATCH,        'Match de Tweets orfãos'),
    (PROC_TAGS,         'Exportação Tags'),
    (PROC_JSON_IMPORT,  'Importação JSON'),
    (PROC_NETWORK,      'Montagem Rede')
)


def stopwords() -> list:
    excecoes = []
    for line in open(BASE_DIR+'/excecoes.txt').readlines():
        for words in line.split(','):
            excecoes.append(words.strip().lower())
    return excecoes


def clean_pontuation(s) -> str:
    result = ''
    for letter in s:
        if letter not in ['.', ',', ':', '?', '!', '"', "'", "”", '“', ')', '(']:
            result += letter
    return result


class Projeto(models.Model):
    nome = models.CharField(max_length=20)
    objetivo = models.TextField('Objetivo')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    grupo = models.ForeignKey(Group, on_delete=models.PROTECT, null=True)
    alcance = models.BigIntegerField('Alcance Estimado', default=0)

    def __str__(self):
        return self.nome

    @property
    def tot_twits(self):
        soma = 0
        for termo in self.termo_set.all():
            soma += termo.last_count
        return '{:,}'.format(soma).replace(',','.')

    @property
    def tot_retwits(self):
        soma = 0
        for termo in self.termo_set.all():
            soma += termo.tot_retwits
        return '{:,}'.format(soma).replace(',','.')

    def top_tweets(self):
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

    def most_common(self, total=100, language='pt'):
        result = Counter()
        excecoes = stopwords()
        for termo in self.termo_set.all():
            # adiciona os termos de busca na exceção para que eles não distorçam o grupamento
            for busca in termo.busca.split():
                excecoes.append(busca)

            # para cada tweet na linguagem definida, montar matriz de ocorrências
            for tweet in termo.tweet_set.filter(retwit_id__isnull=True):
                if tweet.language is not None and tweet.language != language:
                    continue
                palavras = tweet.text.lower().split()
                for palavra in palavras:
                    if not palavra.startswith('http') and not palavra.startswith('@'):
                        palavra_limpa = clean_pontuation(palavra)
                        if palavra_limpa not in excecoes:
                            if len(palavra_limpa) > 3:
                                result[palavra_limpa] += tweet.favorites
        return result.most_common(total)


STATUS_TERMO = (('A', 'Ativo'), ('P', 'Processando'), ('E', 'Erro'),
                ('I', 'Interrompido'), ('C', 'Concluido'))


class Termo(models.Model):
    busca = models.CharField(max_length=200)
    projeto = models.ForeignKey(Projeto, on_delete=models.PROTECT)
    dtinicio = models.DateTimeField('Início da Busca', null=True, blank=True,
                                    help_text='Deixe em branco caso queira iniciar imediatamente')
    dtfinal = models.DateTimeField('Fim da Busca')
    language = models.CharField(max_length=2, null=True, blank=True)
    tipo_busca = models.CharField('Tipo da Busca', max_length=1, choices=TIPO_BUSCA, default=PROC_IMPORTACAO)
    status = models.CharField(max_length=1, choices=STATUS_TERMO, default='A')
    ult_tweet = models.BigIntegerField(null=True, blank=True)
    ult_processamento = models.DateTimeField(null=True, blank=True)  # Última vez que o termo foi processado
    last_count = models.IntegerField('Total de Tweets', default=0)

    def __str__(self):
        return self.busca

    @property
    def tot_twits(self):
        if self.tipo_busca in (PROC_IMPORTACAO, PROC_PREMIUM):
            return self.tweet_set.count() or 0
        else:
            return self.tweetinput_set.count() or 0

    @property
    def tot_retwits(self):
        total = Tweet.objects.filter(termo=self).aggregate(Sum('retweets'))['retweets__sum']
        return total or 0

    @property
    def tot_favorites(self):
        total = Tweet.objects.filter(termo=self).aggregate(Sum('favorites'))['favorites__sum']
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


class Processamento(models.Model):

    AGENDADO = 'A'
    PROCESSANDO = 'P'
    CONCLUIDO = 'C'

    dt = models.DateTimeField()
    tipo = models.CharField(max_length=1, choices=TIPO_PROCESSAMENTO, default=PROC_IMPORTACAO)
    termo = models.ForeignKey(Termo, on_delete=models.CASCADE, null=True)
    twit_id = models.CharField('Último Tweet associado', max_length=21, blank=True, null=True)
    status = models.CharField(max_length=1, choices=((AGENDADO, 'Agendado'),
                                                     (PROCESSANDO, 'Em processamento'),
                                                     (CONCLUIDO, 'Concluído')), default=CONCLUIDO, db_index=True)

    def __str__(self):
        return '%s: %s' % (self.dt, self.termo if self.termo else self.tipo)

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


class TweetUser(models.Model):
    twit_id = models.BigIntegerField(primary_key=True)
    username = models.CharField(max_length=100, null=True, db_index=True)
    name = models.CharField(max_length=200, null=True)
    location = models.CharField(max_length=200, null=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateField(null=True, blank=True)
    followers = models.BigIntegerField(default=0)

    def __str__(self):
        return u'%s (%s)' % (self.username, self.name)

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
    text = models.CharField(max_length=2048)
    created_time = models.DateTimeField()
    retweets = models.IntegerField()
    favorites = models.IntegerField()
    # quotes = models.IntegerField()
    user = models.ForeignKey(TweetUser, on_delete=models.CASCADE)
    termo = models.ForeignKey(Termo, on_delete=models.SET_NULL, null=True)
    retwit_id = models.CharField(max_length=21, null=True) # Parent Tweet
    language = models.CharField(max_length=5, null=True)
    location = models.TextField(null=True, blank=True)
    geo = models.CharField(max_length=150, null=True, blank=True)

    def __str__(self):
        return self.twit_id

    @property
    def url(self):
        return mark_safe("<a href='https://twitter.com/i/web/status/%s' target='_blank'>Link</a>" % self.twit_id)


# Aqui estão os retweet, reply_to (comentários) ou quote (retweet com comentário)
# O tweet original pode ser importado após o retweet. Dessa forma, nem todo retweet tem associação com o Tweet
# Desta forma, uma rotina pós-exportação deve regularmente verificar se já é possível realizar a associação
class Retweet(models.Model):
    REPLY = 'C'    # Comentário
    QUOTE = 'Q'    # Retweet com comentário
    RETWEET = 'R'  # Retweet sem comentário
    retweet_id = models.CharField(max_length=21, null=True, blank=True, db_index=True)    # id do retweet
    parent_id = models.CharField(max_length=21, null=True, blank=True, db_index=True)     # parent id
    user = models.ForeignKey(TweetUser, on_delete=models.PROTECT)          # user do retweet
    tweet = models.ForeignKey(Tweet, on_delete=models.SET_NULL, null=True) # Tweet original que gerou o retweet
    created_time = models.DateTimeField(null=True)
    type = models.CharField(max_length=1,
                            choices=((REPLY, 'Reply'), (QUOTE, 'Quote'), (RETWEET, 'Retweet')),
                            null=True, blank=True)

    def __str__(self):
        return self.retweet_id

    # Intervalo de tempo entre a postagem original e o retweet (em minutos)
    def tweet_dif(self):
        if self.tweet:
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
    termo = models.ForeignKey(Termo, on_delete=models.SET_NULL, blank=True, null=True)

