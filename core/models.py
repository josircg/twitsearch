from collections import Counter

from django.db import models, connection
from django.db.models import Sum
from django.contrib.auth.models import User, Group
from django.utils.safestring import mark_safe

from core import clean_pontuation, stopwords

PROC_IMPORTACAO = 'I'   # Importação via busca regular
PROC_PREMIUM = 'A'      # Importação Premium
PROC_YOUTUBE = 'Y'      # Importação Youtube
PROC_RAPID = 'D'        # Importação Rapid API
PROC_IMPORTUSER = 'U'   # Busca na rede tweets de um determinado usuário
PROC_RETWEET = 'R'      # Busca na rede retweets de um determinado tweet
PROC_BUSCAGLOBAL = 'G'  # Busca na base de dados, tweets que atendam a um critério de busca
PROC_OPENSEARCH = 'O'   # Busca na base do OpenSearch/ElasticSearch
PROC_FILTROPROJ = 'P'   # Filtro dentro do projeto
PROC_ESTIMATE = 'E'     # Calcula estimativa de tweets
PROC_MATCH = 'M'        # Faz o match de tweets orfãos de projeto
PROC_TAGS = 'T'         # Geração de arquivo CSV com as TAGs
PROC_NETWORK = 'N'      # Geração de Grafo
PROC_BACKUP = 'B'       # Backup JSON
PROC_JSON_IMPORT = 'J'  # Importação dos JSONs pendentes
PROC_FECHAMENTO = 'F'   # Fechamento do Projeto e cálculo das estatísticas

TIPO_BUSCA = (
    (PROC_PREMIUM,     'Importação Premium'),
    (PROC_IMPORTUSER,  'Importação Usuário'),
    (PROC_BUSCAGLOBAL, 'Busca Global'),
    (PROC_OPENSEARCH,  'OpenSearch'),
    (PROC_FILTROPROJ,  'Busca no Projeto'),
)

TIPO_PROCESSAMENTO = (
    (PROC_IMPORTACAO,   'Importação'),
    (PROC_PREMIUM,      'Importação Twitter'),
    (PROC_YOUTUBE,      'Importação Youtube'),
    (PROC_IMPORTUSER,   'Importação User'),
    (PROC_BUSCAGLOBAL,  'Busca Global'),
    (PROC_OPENSEARCH,   'OpenSearch'),
    (PROC_FILTROPROJ,   'Busca no Projeto'),
    (PROC_BACKUP,       'Backup JSON'),
    (PROC_ESTIMATE,     'Calcula Estimativa'),
    (PROC_MATCH,        'Match de Tweets orfãos'),
    (PROC_TAGS,         'Exportação Tags'),
    (PROC_JSON_IMPORT,  'Importação JSON'),
    (PROC_NETWORK,      'Montagem Rede')
)

STATUS_TERMO = (('A', 'Ativo'), ('P', 'Processando'), ('E', 'Erro'),
                ('I', 'Interrompido'), ('C', 'Concluido'))


class Rede(models.Model):
    nome = models.CharField(max_length=100)
    ativa = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class Projeto(models.Model):
    nome = models.CharField(max_length=40)
    objetivo = models.TextField('Objetivo')
    alcance = models.BigIntegerField('Alcance Estimado', default=0)
    language = models.CharField(max_length=4, null=True, blank=True)  # Idioma default
    tot_twits = models.IntegerField('Total Lido', null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    grupo = models.ForeignKey(Group, on_delete=models.PROTECT, null=True)
    status = models.CharField(max_length=1, choices=STATUS_TERMO, default='A')
    redes = models.ManyToManyField(Rede, blank=True)
    prefix = models.CharField('Elastic Prefix', max_length=20, blank=True)
    stopwords = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.nome

    @property
    def tot_calculado(self):
        soma = 0
        for termo in self.termo_set.all():
            soma += termo.last_count
        return soma

    @property
    def tot_estimado(self):
        soma = self.termo_set.aggregate(Sum('estimativa'))['estimativa__sum']
        if soma:
            return '{:,}'.format(soma).replace(',', '.')
        else:
            return '-'
    tot_estimado.fget.short_description = 'Estimativa'

    @property
    def tot_retwits(self):
        soma = 0
        if self.termo_set.count() > 50:
            return 'Calculating...'
        else:
            for termo in self.termo_set.all():
                soma += termo.tot_retwits
            return '{:,}'.format(soma).replace(',','.')
    tot_retwits.fget.short_description = 'Retweets'

    @property
    def termos_processados(self):
        return self.termo_set.filter(status='C').count()

    @property
    def termos_ativos(self):
        return self.termo_set.filter(status='A').count()
    termos_ativos.fget.short_description = 'Termos Ativos'

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


    def most_common(self, total=100):
        result = Counter()
        excecoes = stopwords()
        for termo in self.termo_set.all():
            # adiciona os termos de busca na exceção para que eles não distorçam o grupamento
            for busca in termo.busca.split():
                excecoes.append(busca)

            for tweet in Tweet.objects.filter(tweetinput__termo__id=termo.id).only('language','text'):
                if termo.language and tweet.language and tweet.language != termo.language:
                    continue
                palavras = tweet.text.lower().split()
                for palavra in palavras:
                    if not palavra.startswith('http') and not palavra.startswith('@'):
                        palavra_limpa = clean_pontuation(palavra)
                        if palavra_limpa not in excecoes:
                            if len(palavra_limpa) > 3:
                                result[palavra_limpa] += tweet.favorites
        return result.most_common(total)

    @property
    def total_views(self):
        return Tweet.objects.filter(tweetinput__termo__projeto_id=self.pk).aggregate(soma=Sum('imprints'))['soma']


class Termo(models.Model):
    descritivo = models.CharField(max_length=100, blank=True, null=True)
    busca = models.CharField(max_length=2000)
    projeto = models.ForeignKey(Projeto, on_delete=models.PROTECT)
    dtinicio = models.DateTimeField('Início da Busca', null=True, blank=True,
                                    help_text='Deixe em branco caso queira iniciar imediatamente')
    dtfinal = models.DateTimeField('Fim da Busca', null=True, blank=True)
    language = models.CharField(max_length=2, null=True, blank=True)
    tipo_busca = models.CharField('Tipo da Busca', max_length=1, choices=TIPO_BUSCA, default=PROC_IMPORTACAO)
    status = models.CharField(max_length=1, choices=STATUS_TERMO, default='A')
    ult_tweet = models.BigIntegerField(null=True, blank=True)        # Utilizado para a estratégia contínua
    ult_processamento = models.DateTimeField(null=True, blank=True)  # Última vez que o crawler foi executado
    last_count = models.IntegerField('Total de Tweets', default=0)
    estimativa = models.IntegerField('Total Estimado', default=0)

    def __str__(self):
        return self.busca

    @property
    def tot_twits(self):
        if self.last_count:
            return self.last_count
        else:
            return self.tweetinput_set.count() or 0

    @property
    def tot_retwits(self):
        with connection.cursor() as cursor:
            cursor.execute(
            'select sum(retweets) from core_tweet as t, core_tweetinput as ti'
            ' where ti.tweet_id = t.twit_id and ti.termo_id = %s', [self.id ])
            total = cursor.fetchone()[0]
        return total or 0

    @property
    def tot_favorites(self):
        with connection.cursor() as cursor:
            cursor.execute(
            'select sum(favorites) from core_tweet as t, core_tweetinput as ti'
            ' where ti.tweet_id = t.twit_id and ti.termo_id = %s', [self.id ])
            total = cursor.fetchone()[0]
        return total or 0

    @property
    def unique_users(self):
        with connection.cursor() as cursor:
            cursor.execute("select count(distinct user_id) from" +
                           "(select distinct t.user_id from core_tweet t, core_tweetinput i"
                           " where i.termo_id = %s and t.twit_id = i.tweet_id" +
                           " union " +
                           " select distinct r.user_id from core_tweetinput i, core_retweet as r" +
                           " where i.termo_id = %s and i.tweet_id = r.parent_id) as uniao",
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
    tot_registros = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return '%s: %s' % (self.dt, self.termo if self.termo else self.tipo)

    @property
    def tot_twits(self):
        if self.tot_registros:
            return self.tot_registros
        else:
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
        if self.username:
            return self.username
        else:
            return f'ID {self.twit_id}'

    class Meta:
        verbose_name = 'Usuário do Twitter'
        verbose_name_plural = 'Usuários do Twitter'
        ordering = ['twit_id', ]


class FollowersHistory(models.Model):
    user = models.ForeignKey(TweetUser, on_delete=models.CASCADE)
    followers = models.BigIntegerField(null=True)
    following = models.BigIntegerField(null=True)
    favourites = models.BigIntegerField(null=True)
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
    retweets = models.IntegerField(null=True)
    favorites = models.IntegerField(null=True)
    quotes = models.IntegerField(null=True)
    imprints = models.IntegerField(null=True)
    user = models.ForeignKey(TweetUser, on_delete=models.CASCADE)
    termo = models.ForeignKey(Termo, on_delete=models.SET_NULL, null=True) # Termo que trouxe o tweet
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
    user = models.ForeignKey(TweetUser, on_delete=models.PROTECT)                         # user do retweet
    related_user = models.ForeignKey(TweetUser, related_name='related_user',
                                     on_delete=models.SET_NULL, null=True, blank=True)
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


# Quais os tweets que foram recuperados a partir de uma busca
class TweetInput(models.Model):
    tweet = models.ForeignKey(Tweet, on_delete=models.CASCADE)
    termo = models.ForeignKey(Termo, on_delete=models.CASCADE, blank=True, null=True)
    processamento = models.ForeignKey(Processamento, on_delete=models.CASCADE)
    exported = models.BooleanField(default=False)

    class Meta:
        unique_together = ["tweet", "termo"]