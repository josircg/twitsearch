from django.db import models
from django.contrib.auth.models import User


class Categoria(models.Model):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome

    @property
    def tot_canais(self):
        return self.canal_set.all().count()
    tot_canais.fget.short_description = 'Total de Canais'


class Canal(models.Model):

    class Status(models.TextChoices):
        ATIVO = 'A', 'Ativo'
        PROCESSANDO = 'P', 'Em processamento'
        NAO_EXISTE = 'D', 'Não existe mais'
        INATIVO = 'I', 'Inativo'  # Sem mensagens

    username = models.CharField(max_length=255, db_index=True, unique=True)
    id_numerico = models.BigIntegerField(db_index=True, unique=True, null=True, blank=True)
    titulo = models.TextField(null=True, blank=True)
    sobre = models.TextField(blank=True, null=True)
    categorias = models.ManyToManyField(Categoria, blank=True)
    num_participantes = models.IntegerField('Tot.Participantes',default=0)
    num_mensagens = models.BigIntegerField('Tot.Mensagens', default=0)
    megagroup = models.BooleanField(default=False)
    localizacao = models.CharField('Localização', max_length=200, null=True, blank=True)
    verificado = models.BooleanField('Verificado pelo Telegram', default=False)
    dtcriacao = models.DateTimeField('Dt.Criação', null=True, blank=True)
    ultima_mensagem = models.BigIntegerField(null=True, blank=True)
    dt_ultima_carga = models.DateTimeField('Útlima carga', null=True, blank=True)
    access_hash = models.CharField(max_length=64, null=True, blank=True)
    status = models.CharField(max_length=1, choices=Status.choices, default='A')

    class Meta:
        verbose_name_plural = 'Canais'

    def __str__(self):
        return self.username


class APIKeys(models.Model):

    class Status(models.TextChoices):
        ATIVO = 'A', 'Ativo'
        ERRO = 'E', 'Inválida'

    user = models.ForeignKey(User, on_delete=models.PROTECT)
    titulo = models.CharField('Título', max_length=100)
    telefone = models.CharField('Telefone (+PaisNumero)', max_length=15, null=True, blank=True)
    api_id = models.IntegerField()
    api_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=1, choices=Status.choices, default='A')

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = 'Chave de API'
        verbose_name_plural = 'Chaves de API'


class Lista(models.Model):
    nome = models.CharField(max_length=100)
    dono = models.ForeignKey(User, on_delete=models.PROTECT)
    publica = models.BooleanField('Qualquer usuário pode utilizá-la', default=False)
    canais = models.ManyToManyField(Canal, blank=True)

    def __str__(self):
        return self.nome

    @property
    def tot_canais(self):
        return self.canais.all().count()
